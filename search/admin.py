from django.contrib import admin
from search.models import SearchField
from search.models import SearchQuery

admin.site.register(SearchField)
admin.site.register(SearchQuery)
