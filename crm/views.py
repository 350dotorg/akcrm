from actionkit import Client
from actionkit.models import *
from django.conf import settings
from django.db import connections
from django.db.models import Count
from django.contrib import messages
from djangohelpers import rendered_with, allow_http
from django.http import HttpResponseNotFound, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import date
from django.utils.simplejson import JSONEncoder
import datetime
import dateutil.parser
import json
import os.path
import re

from akcrm.crm.forms import ContactForm
from akcrm.crm.models import ContactRecord
from akcrm.permissions import authorize

@authorize("add_contact_record")
@allow_http("POST")
@rendered_with("_form.html")
def contacts_for_user(request, akid):
    akid = [i for i in request.POST.getlist('akid') if i and i.strip()][0]
    post = request.POST.copy()
    post['akid'] = akid
    form = ContactForm(data=post)
    if form.is_valid():
        contact = form.save()
        messages.success(request, u'Contact saved')
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    else:
        return locals()

def contact_record(request, contact_id):
    contact = get_object_or_404(ContactRecord, id=contact_id)

    
