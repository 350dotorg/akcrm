from actionkit import Client
from django.conf import settings
from django.db.models import Count
from django.http import HttpResponseNotFound, HttpResponse, HttpResponseRedirect
from djangohelpers import rendered_with, allow_http
from actionkit.models import *
import json
import os.path
import re
import datetime
from django.template.defaultfilters import date
from django.utils.simplejson import JSONEncoder

QUERIES = {
    'country': {
        'query': "country",
        },
    'region': {
        'query': "region",
        },
    'state': {
        'query': "state",
        },
    'city': {
        'query': "city",
        },
    'action': {
        'query': "actions__page__id",
        },
    'tag': {
        'query': "actions__page__pagetags__tag__id",
        },
    'organization': {
        'query': "fields__value",
        'extra': {"fields__name": "organization"},
        },
    'skills': {
        'query': "fields__value",
        'extra': {"fields__name": "skills"},
        },
    'engagement_level': {
        'query': "fields__value",
        'extra': {"fields__name": "engagement_level"},
        },
    }

@allow_http("GET")
def countries(request):
    countries = CoreUser.objects.using("ak").values_list("country", flat=True).distinct().order_by("country")
    countries = [(i,i) for i in countries]
    return HttpResponse(json.dumps(countries), 
                        content_type="application/json")

@allow_http("GET")
def regions(request):
    countries = request.GET.getlist("country")
    raw_regions = CoreUser.objects.using("ak").filter(
        country__in=countries).values(
        "country", "region").distinct().order_by("country", "region")
    regions = {}
    for region in raw_regions:
        if region['country'] not in regions:
            regions[region['country']] = []
        regions[region['country']].append(region['region'])
    return HttpResponse(json.dumps(regions), 
                        content_type="application/json")

@allow_http("GET")
def states(request):
    states = CoreUser.objects.using("ak").values_list("state", flat=True).distinct().order_by("state")
    states = [(i,i) for i in states]
    return HttpResponse(json.dumps(states), 
                        content_type="application/json")

@allow_http("GET")
def cities(request):
    cities = CoreUser.objects.using("ak").values_list("city", flat=True).distinct().order_by("city")
    cities = [(i,i) for i in cities]
    return HttpResponse(json.dumps(cities), 
                        content_type="application/json")

@allow_http("GET")
def pages(request):
    pages = CorePage.objects.using("ak").all().order_by("title")
    pages = [(i.id, str(i)) for i in pages]
    return HttpResponse(json.dumps(pages), 
                        content_type="application/json")


@allow_http("GET")
@rendered_with("home.html")
def home(request):
    tags = CoreTag.objects.using("ak").all().order_by("name")
    countries = CoreUser.objects.using("ak").values_list("country", flat=True).distinct().order_by("country")

    pages = CorePage.objects.using("ak").all().order_by("title")

    organizations = CoreUserField.objects.using("ak").filter(name="organization").values_list("value", flat=True).distinct().order_by("value")

    skills = CoreUserField.objects.using("ak").filter(name="skills").values_list("value", flat=True).distinct().order_by("value")

    fields = {
        'Location':
            (('country', 'Country'),
             ('region', 'Region', 'disabled'),
             ('state', 'State', 'disabled'),
             ('city', 'City', 'disabled'),
             ),
        'Activity':
            (('action', 'Took part in action'),
             ('tag', 'Is tagged with'),
             ),
        'About':
            (('organization', "Organization"),
             ('skills', "Skills"),
             ),
        }

    return locals()

@allow_http("GET")
@rendered_with("search.html")
def search(request):
    ctx = _search(request)
    users = ctx['users']
    
    return ctx

def search_raw_sql(request):
    users = _search(request)['users']

    akids = users.values_list("id", flat=True)
    akids = list(akids)

    from django.db import connections
    query = connections['ak'].queries[0]['sql']

    ctx = dict(
        akids=akids,
        query=query
        )

    return HttpResponse(query, content_type="text/plain")

@allow_http("GET")
def search_just_akids(request):
    users = _search(request)['users']

    akids = users.values_list("id", flat=True).distinct()
    akids = set(list(akids))

    akids = ", ".join(str(i) for i in akids)
    return HttpResponse(akids, content_type="text/plain")

def _search(request):
    base_user_query = CoreUser.objects.using("ak").order_by(
        "id")
    
    includes = []

    include_pattern = re.compile("^include:\d+$")
    for key in request.GET.keys():
        if include_pattern.match(key) and request.GET[key]:
            includes.append((key, request.GET.getlist(key)))

    human_query = []

    all_user_queries = []
    for include_group in includes:
        users = base_user_query.all()
        _human_query = []
        for item in include_group[1]:
            possible_values = request.GET.getlist(
                "%s_%s" % (include_group[0], item))
            if len(possible_values) == 0:
                continue
            query_data = QUERIES[item]
            query_item = query_data['query']
            query = {
                query_item + "__in": possible_values
            }
            if query_data.get("extra"):
                query.update(query_data['extra'])
            users = users.filter(**query)
            _human_query.append("%s is in %s" % (item, possible_values))
        all_user_queries.append(users)
        human_query.append("(%s)" % " and ".join(_human_query))

    human_query = "\n or ".join(human_query)
    users = None
    for i, query in enumerate(all_user_queries):
        if i == 0:
            users = query
        else:
            users = users | query
    if users is None:
        users = base_user_query
    users = users.prefetch_related("fields", "phones")

    ctx = dict(includes=includes,
               params=request.GET)

    ### If both of user_name and user_email are filled out,
    ### search for anyone who matches EITHER condition, rather than both.
    extra_where = []
    extra_params = []
    if request.GET.get("user_name"):
        extra_where.append(
            "CONCAT(`core_user`.`first_name`, ' ', `core_user`.`last_name`) LIKE %s")
        extra_params.append("%" + "%".join(request.GET['user_name'].split()) + "%")
        human_query += "\n and name is like \"%s\"" % request.GET['user_name']
    if request.GET.get("user_email"):
        extra_where.append("`core_user`.`email` LIKE %s")
        extra_params.append("%" + request.GET.get("user_email") + "%")
        human_query += "\n and email is like \"%s\"" % request.GET['user_email']
    if len(extra_where):
        if len(extra_where) == 2:
            extra_where = ["(%s OR %s)" % tuple(extra_where)]
        users = users.extra(
            where=extra_where,
            params=extra_params)

    ctx['human_query'] = human_query
    ctx['users'] = users
    ctx['request'] = request
    request.session['akcrm.query'] = request.GET.urlencode()
    return ctx

@allow_http("GET")
@rendered_with("detail.html")
def detail(request, user_id):
    return _detail(request, user_id)

@allow_http("GET")
def detail_json(request, user_id):
    ctx = _detail(request, user_id)
    def dthandler(obj):
        if isinstance(obj, datetime.datetime):
            return date(obj)
        elif hasattr(obj, 'to_json'):
            return obj.to_json()
    agent = ctx['agent']
    try:
        ctx['latest_action'] = ctx['actions'][0]
    except IndexError:
        ctx['latest_action'] = None
    try:
        ctx['latest_order'] = ctx['orders'][0]
    except IndexError:
        ctx['latest_order'] = None
    try:
        ctx['latest_send'] = ctx['sends'][0]
    except IndexError:
        ctx['latest_send'] = None
    try:
        ctx['latest_open'] = ctx['opens'][0]
    except IndexError:
        ctx['latest_open'] = None
    try:
        ctx['latest_click'] = ctx['clicks'][0]
    except IndexError:
        ctx['latest_click'] = None


    return HttpResponse(json.dumps(ctx, cls=JSONEncoder, default=dthandler),
                        content_type="application/json")
    
    
def _detail(request, user_id):
    try:
        agent = CoreUser.objects.using("ak").get(id=user_id)
    except CoreUser.DoesNotExist:
        return HttpResponseNotFound("No such record exists")

    actions = list(agent.actions.all().select_related("page").order_by("-created_at"))
    orders = list(agent.orders.all().select_related("action", "action__page").order_by("-created_at"))
    
    clicks = clicks_by_user(agent)
    opens = opens_by_user(agent)
    sends = CoreUserMailing.objects.using("ak").filter(user=agent).order_by("-created_at").select_related("subject")

    query = request.session.get('akcrm.query')

    return locals()


@allow_http("GET")
def mailing_history(request, user_id):
    try:
        agent = CoreUser.objects.using("ak").get(id=user_id)
    except CoreUser.DoesNotExist:
        return HttpResponseNotFound("No such record exists")

    _sends = mailings_by_user(agent)

    sends = {}
    for send in _sends:
        id = send['id']
        if id not in sends:
            sends[id] = {
                'id': send['id'],
                'mailed_at': send['mailed_at'],
                'subject_text': send['subject_text'],
                'clicks': set(),
                'opens': set(),
                }
        sends[id]['clicks'] = set(sends[id]['clicks'])
        sends[id]['opens'] = set(sends[id]['opens'])
        if send['clicked_at'] is not None:
            sends[id]['clicks'].add(send['clicked_at'])
        if send['opened_at'] is not None:
            sends[id]['opens'].add(send['opened_at'])
        sends[id]['clicks'] = list(sends[id]['clicks'])
        sends[id]['opens'] = list(sends[id]['opens'])
    
    def dthandler(obj):
        if isinstance(obj, datetime.datetime):
            return date(obj)
    return HttpResponse(json.dumps(sends, default=dthandler),
                        content_type="application/json")


from actionkit.utils import get_client

@allow_http("POST")
def edit_skills(request, user_id):
    try:
        agent = CoreUser.objects.using("ak").get(id=user_id)
    except CoreUser.DoesNotExist:
        return HttpResponseNotFound("No such record exists")

    skills = request.POST.getlist("skills")

    actionkit = get_client()
    user = actionkit.User.save({'id': user_id, 'user_skills': skills})
    return HttpResponse(json.dumps(user['custom_fields'].get("skills", [])),
                        content_type="text/plain")
