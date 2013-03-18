from akcrm.search.models import SearchField
from akcrm.search.models import SearchQuery
from akcrm.search.models import ActiveReport
from django.contrib import admin
from djangohelpers.lib import register_admin as register

register(SearchField)
register(SearchQuery)
register(ActiveReport)
