from actionkit import Client
from actionkit.models import *
from django.conf import settings
from django.db import connections
from django.db.models import Count
from django.contrib import messages
from djangohelpers import rendered_with, allow_http
from django.http import HttpResponseNotFound, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.defaultfilters import date
from django.utils.simplejson import JSONEncoder
import datetime
import dateutil.parser
import json
import os.path
import re

from akcrm.cms.models import AllowedTag
from akcrm.cms.forms import AllowedTagForm
from akcrm.permissions import authorize

@authorize("add_allowed_tags")
@allow_http("GET", "POST")
@rendered_with("cms/allowed_tags.html")
def allowed_tags(request):
    if request.method == "GET":

        allowed_tags = [t.ak_tag_id for t in AllowedTag.objects.all()]
        allowed_tags = CoreTag.objects.using("ak").filter(id__in=allowed_tags)

        form = AllowedTagForm()
        return locals()

    form = AllowedTagForm(data=request.POST)
    if not form.is_valid():
        return locals()

    tag = form.save()
    messages.success(request, u'Tags added')
    return redirect(".")
