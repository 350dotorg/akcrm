from django.contrib import admin
from akcrm.search.models import SearchField
from akcrm.search.models import SearchQuery

admin.site.register(SearchField)
admin.site.register(SearchQuery)
