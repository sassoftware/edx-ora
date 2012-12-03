import ConfigParser
from django.conf import settings
from metrics.timing_functions import finalize_timing
from models import Submission, Grader
import logging
from models import GraderStatus, SubmissionState
import expire_submissions
from django.utils import timezone
from metrics import metrics_util
from statsd import statsd
import json

log = logging.getLogger(__name__)

def create_grader(grader_dict,sub):

    grade = Grader(
        score=grader_dict['score'],
        feedback=grader_dict['feedback'],
        status_code=grader_dict['status'],
        grader_id=grader_dict['grader_id'],
        grader_type=grader_dict['grader_type'],
        confidence=grader_dict['confidence'],
        submission=sub,
    )

    grade.save()

    return grade

def create_and_handle_grader_object(grader_dict):
    """
    Creates a Grader object and associates it with a given submission
    Input is grader dictionary with keys:
     feedback, status, grader_id, grader_type, confidence, score,submission_id, errors
        Feedback should be a dictionary with as many keys as needed.
        Errors is a string containing errors.
    """

    for tag in ["feedback", "status", "grader_id", "grader_type", "confidence", "score", "submission_id", "errors"]:
        if tag not in grader_dict:
            return False, "{0} tag not in input dictionary.".format(tag)

    try:
        sub = Submission.objects.get(id=grader_dict['submission_id'])
    except:
        return False, "Error getting submission."

    log.debug(grader_dict['feedback'])

    try:
        grader_dict['feedback']=json.loads(grader_dict['feedback'])
    except:
        pass

    if not isinstance(grader_dict['feedback'],dict):
        grader_dict['feedback']={'feedback' : grader_dict['feedback']}

    if grader_dict['status']==GraderStatus.failure:
        grader_dict['feedback']=' '.join(grader_dict['errors'])

    grader_dict['feedback']=json.dumps(grader_dict['feedback'])

    grade=create_grader(grader_dict,sub)

    #TODO: Need some kind of logic somewhere else to handle setting next_grader

    sub.previous_grader_type = grade.grader_type
    sub.next_grader_type = grade.grader_type

    #TODO: Some kind of logic to decide when sub is finished grading.

    #If submission is ML or IN graded, and was successful, state is finished
    if(grade.status_code == GraderStatus.success and grade.grader_type in ["IN", "ML"]):
        sub.state = SubmissionState.finished
    elif(grade.status_code == GraderStatus.success and grade.grader_type in ["PE"]):
        #If grading type is Peer, and was successful, check to see how many other times peer grading has succeeded.
        successful_peer_grader_count = sub.get_successful_peer_graders().count()
        #If number of successful peer graders equals the needed count, finalize submission.
        if successful_peer_grader_count >= settings.PEER_GRADER_COUNT:
            sub.state = SubmissionState.finished
    #If something fails, immediately mark it for regrading
    #TODO: Get better logic for handling failure cases
    elif(grade.status_code == GraderStatus.failure and sub.state==SubmissionState.being_graded):
        number_of_failures=sub.get_unsuccessful_graders().count()
        #If it has failed too many times, just return an error
        if number_of_failures>settings.MAX_NUMBER_OF_TIMES_TO_RETRY_GRADING:
            expire_submissions.finalize_expired_submission(sub)
        else:
            sub.state=SubmissionState.waiting_to_be_graded

    #Increment statsd whenever a grader object is saved.
    statsd.increment("open_ended_assessment.grading_controller.controller.create_grader_object",
        tags=["submission_state:{0}".format(sub.state),
              "grader_type:{0}".format(grade.grader_type),
              "grader_status:{0}".format(grade.status_code),
              "location:{0}".format(sub.location),
              "course_id:{0}".format(sub.course_id),
              "next_grader_type:{0}".format(sub.next_grader_type),
              "score:{0}".format(grade.score),
        ]
    )

    sub.save()

    #Insert timing finalization code
    finalize_timing(sub,grade)

    return True, {'submission_id': sub.xqueue_submission_id, 'submission_key': sub.xqueue_submission_key}


def get_grader_settings(settings_file):
    """
    Reads grader settings from a given file
    Output:
        Dictionary containing all grader settings
    """
    config = ConfigParser.RawConfigParser()
    config.read(settings_file)
    grader_type = config.get("grading", "grader_type")

    grader_settings = {
        'grader_type': grader_type,
    }

    return grader_settings