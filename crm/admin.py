from django.contrib import admin

from akcrm.crm.models import ContactRecord
from akcrm.crm.models import HomePageHtml

admin.site.register(ContactRecord)
admin.site.register(HomePageHtml)
