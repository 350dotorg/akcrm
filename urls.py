from django.conf.urls.defaults import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    'akcrm.search.views',
    url(r'^$', 'home', name='home'),

    url(r'^choices/countries/$', 'countries', name='choices_countries'),
    url(r'^choices/regions/$', 'regions', name='choices_regions'),
    url(r'^choices/states/$', 'states', name='choices_states'),
    url(r'^choices/cities/$', 'cities', name='choices_cities'),
    url(r'^choices/pages/$', 'pages', name='choices_pages'),

    url(r'^search/$', 'search', name='search'),
    url(r'^search/sql/$', 'search_raw_sql', name='search_raw_sql'),
    url(r'^search/akids/$', 'search_just_akids', name='search_just_akids'),
    url(r'^record/(?P<user_id>\d+)/$', 'detail', name='detail'),
    url(r'^record/(?P<user_id>\d+)/json/$', 'detail_json', name='detail_json'),

    url(r'^record/(?P<user_id>\d+)/skills/$', 'edit_skills', 
        name='edit_skills'),

    url(r'^record/(?P<user_id>\d+)/mailing_history/$', 
        'mailing_history', name='mailing_history'),

    url(r'^admin/', include(admin.site.urls)),
    )

urlpatterns += patterns(
    'django.contrib.auth.views',
    (r'^accounts/login/$', 'login'),
    (r'^accounts/logout/$', 'logout'),
)
