from django.conf import settings
from django.conf.urls.defaults import patterns, include, url

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = ('',
    url(r'^$', 'contentstore.views.index', name='index'),
    url(r'^edit_item$', 'contentstore.views.edit_item', name='edit_item'),
    url(r'^save_item$', 'contentstore.views.save_item', name='save_item'),
    url(r'^(?P<org>[^/]+)/(?P<course>[^/]+)/course/(?P<name>[^/]+)$', 'contentstore.views.course_index', name='course_index'),
    url(r'^github_service_hook$', 'github_sync.views.github_post_receive'),
)

if settings.DEBUG:
    ## Jasmine
    urlpatterns=urlpatterns + (url(r'^_jasmine/', include('django_jasmine.urls')),)

urlpatterns = patterns(*urlpatterns)