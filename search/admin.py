from django.contrib import admin
from akcrm.search.models import SearchField
from akcrm.search.models import SearchQuery
from akcrm.search.models import ActiveReport

admin.site.register(SearchField)
admin.site.register(SearchQuery)
admin.site.register(ActiveReport)
