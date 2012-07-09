from django.contrib import admin

from akcrm.cms.models import AllowedTag
from akcrm.cms.models import HomePageHtml

admin.site.register(AllowedTag)
admin.site.register(HomePageHtml)
