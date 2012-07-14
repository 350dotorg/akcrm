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

    url(r'^autocomplete/sources/$', 'sources', name='autocomplete_sources'),

    url(r'^search/$', 'search', name='search'),
    url(r'^search/json/$', 'search_json', name='search_json'),

    url(r'^search/sql/$', 'search_raw_sql', name='search_raw_sql'),
    url(r'^search/count/$', 'search_count', name='search_count'),
    url(r'^search/akids/$', 'search_just_akids', name='search_just_akids'),
    url(r'^search/csv/$', 'search_csv', name='search_csv'),
    url(r'^search/save/$', 'search_save', name='search_save'),

    url(r'^record/(?P<user_id>\d+)/$', 'detail', name='detail'),
    url(r'^record/(?P<user_id>\d+)/json/$', 'detail_json', name='detail_json'),

    url(r'^record/(?P<user_id>\d+)/skills/$', 'edit_skills', 
        name='edit_skills'),

    url(r'^record/(?P<user_id>\d+)/tags/(?P<tag_id>\d+)/add/$', 'add_user_tag',
        name='add_user_tag'),
    url(r'^record/(?P<user_id>\d+)/tags/(?P<tag_id>\d+)/remove/$', 'remove_user_tag',
        name='remove_user_tag'),

    url(r'^record/(?P<user_id>\d+)/tags/s/(?P<tag_id>\d+)/remove/$', 'remove_user_tag_safe',
        name='remove_user_tag_safe'),
    url(r'^record/(?P<user_id>\d+)/tags/u/(?P<tag_id>\d+)/remove/$', 'remove_user_tag_unsafe',
        name='remove_user_tag_unsafe'),
    
    url(r'^record/(?P<user_id>\d+)/mailing_history/$', 
        'mailing_history', name='mailing_history'),

    url(r'^admin/', include(admin.site.urls)),
    )

urlpatterns += patterns(
    'akcrm.crm.views',
    url(r'^contacts/(?P<akid>\d+)/$', 'contacts_for_user', name='contacts_for_user'),
    )

urlpatterns += patterns(
    'akcrm.cms.views',
    url(r'^tags/$', 'allowed_tags', name='allowed_tags'),
    )

urlpatterns += patterns(
    'django.contrib.auth.views',
    (r'^accounts/login/$', 'login'),
    (r'^accounts/logout/$', 'logout'),
)
