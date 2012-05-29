from actionkit import Client
from actionkit.models import *
from actionkit import rest
from collections import namedtuple
from django.conf import settings
from django.db import connections
from django.db.models import Count
from djangohelpers import rendered_with, allow_http
from django.http import HttpResponseNotFound, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import date
from django.utils.simplejson import JSONEncoder
import datetime
import dateutil.parser
import json
import os.path
import re
from operator import itemgetter

from akcrm.cms.models import AllowedTag
from akcrm.crm.forms import ContactForm
from akcrm.crm.models import ContactRecord
from akcrm.search.utils import clamp
from akcrm.search.utils import latlon_bbox
from akcrm.search.utils import zipcode_to_latlon

def make_default_user_query(query_data, values, search_on, extra_data={}):
    """
    given a query_data dict and values which come from the ui,
    generate a dict that will be used for a user query

    this default query is a within query, that optionally adds some
    extra key/value data to the query dict
    """

    query = {}

    query_str = query_data['query']
    within = query_str + '__in'
    query[within] = values

    extra_info = query_data.get('extra')
    if extra_info:
        query.update(extra_info)

    human_query = "%s is in %s" % (search_on, values)
    return query, human_query

def make_date_query(query_data, values, search_on, extra_data={}):
    date = values[0]
    match = dateutil.parser.parse(date)
    human_query = "%s is in %s" % (search_on, values)
    return {query_data['query']: match}, human_query

def make_zip_radius_query(query_data, values, search_on, extra_data={}):
    zipcode = values[0]
    zipcode = int(zipcode)
    if 'distance' in extra_data:
        distance = extra_data['distance']
        distance = float(distance)
        assert distance > 0, "Bad distance"
        latlon = zipcode_to_latlon(zipcode)
        assert latlon is not None, "No location found for: %s" % zipcode
        lat, lon = latlon
        bbox = latlon_bbox(lat, lon, distance)
        assert bbox is not None, "Bad bounding box for latlon: %s,%s" % (lat, lon)
        lat1, lat2, lon1, lon2 = bbox
        return ({'location__latitude__range': (lat1, lat2),
                 'location__longitude__range': (lon1, lon2)},
                "within %s miles of %s" % (distance, zipcode)
                )
    else:
        return {'zip': zipcode}, "in zip code %s" % zipcode

def make_contact_history_query(query_data, values, search_on, extra_data={}):
    contacted_since = values[0]
    match = dateutil.parser.parse(contacted_since)
    search = ContactRecord.objects.filter(completed_at__gt=match)
    human_query = ["contacted since %s" % contacted_since]
    if 'contacted_by' in extra_data:
        contacted_by = extra_data['contacted_by']
        search = search.filter(user__username=contacted_by)
        human_query.append("by %s" % contacted_by)
    akids = list(search.values_list("akid", flat=True))
    if len(akids) == 0:
        ## TODO give a helpful error message, not a mysterious always-null query
        akids = [0]
    return {'id__in': akids}, " ".join(human_query)

        
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
    'source': {
        'query': "source",
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
    'language': {
        'query': "lang__id",
        },
    'created_before': {
        'query': "created_at__lte",
        'query_fn': make_date_query,
        },
    'created_after': {
        'query': "created_at__gte",
        'query_fn': make_date_query,
        },
    'zipcode': {
        'query_fn': make_zip_radius_query,
        },
    'contacted_since': {
        'query_fn': make_contact_history_query,
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
    countries = request.GET.getlist("country")
    raw_states = CoreUser.objects.using("ak").filter(
        country__in=countries).values(
        "country", "state").distinct().order_by("country", "state")
    states = {}
    for state in raw_states:
        if state['country'] not in states:
            states[state['country']] = []
        states[state['country']].append(state['state'])
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
def sources(request):
    prefix = request.GET.get('q')
    limit = request.GET.get('limit', '10')
    try:
        limit = int(limit)
    except ValueError:
        limit = 10
    limit = clamp(limit, 1, 1000)
    if prefix:
        cursor = connections['ak'].cursor()
        prefix = prefix + '%'
        cursor.execute("SELECT distinct source FROM core_user "
                       "WHERE source LIKE %s ORDER BY source LIMIT %s",
                       [prefix, limit])
        sources = [row[0] for row in cursor.fetchall()]
    else:
        sources = []
    return HttpResponse(json.dumps(sources), content_type='application/json')


@allow_http("GET")
@rendered_with("home.html")
def home(request):
    tags = CoreTag.objects.using("ak").all().order_by("name")
    countries = CoreUser.objects.using("ak").values_list("country", flat=True).distinct().order_by("country")

    pages = CorePage.objects.using("ak").all().order_by("title")

    organizations = CoreUserField.objects.using("ak").filter(name="organization").values_list("value", flat=True).distinct().order_by("value")

    skills = CoreUserField.objects.using("ak").filter(name="skills").values_list("value", flat=True).distinct().order_by("value")

    languages = CoreLanguage.objects.using("ak").all().distinct().order_by("name")

    fields = {
        'Location':
            (('country', 'Country'),
             ('state', 'State', 'disabled'),
             ('city', 'City', 'disabled'),
             ('zipcode', 'Zip Code'),
             ),
        'Activity':
            (('action', 'Took part in action'),
             ('source', 'Source'),
             ('tag', 'Is tagged with'),
             ('contacted_since', "Contacted Since"),
             ),
        'About':
            (('organization', "Organization"),
             ('skills', "Skills"),
             ('language', "Preferred Language"),
             ('created_before', "Created Before"),
             ('created_after', "Created After"),
             ),
        }

    return locals()

@allow_http("GET")
@rendered_with("search.html")
def search(request):
    ctx = _search(request)
    users = ctx['users']

    return ctx

@allow_http("GET")
def search_json(request):
    ctx = _search(request)
    users = ctx['users']
    
    users_json = []
    for user in users:
        users_json.append(dict(
                id=user.id,
                url=user.get_absolute_url(),
                name=unicode(user),
                email=user.email,
                phone=unicode(user.phone() or ''),
                country=user.country,
                state=user.state,
                city=user.city,
                organization=user.organization(),
                created_at=user.created_at.strftime("%m/%d/%Y"),
                ))
    users_json = json.dumps(users_json)
    return HttpResponse(users_json, content_type="application/json")

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
        users = base_user_query
        _human_query = []
        for item in include_group[1]:
            ## "distance" is handled in a group with "zipcode", so we ignore it here
            if item == "distance":
                continue
            ## same for "contacted_by", in a group with "contacted_since"
            if item == "contacted_by":
                continue

            possible_values = request.GET.getlist(
                "%s_%s" % (include_group[0], item))
            if len(possible_values) == 0:
                continue
            query_data = QUERIES[item]
            extra_data = {}

            ## XXX special cased zip code and distance
            # these two fields are together, if we have another case like this
            # we should probably formalize this
            if item == "zipcode":
                distance = request.GET.get('%s_distance' % include_group[0])
                if distance:
                    extra_data['distance'] = distance

            ## XXX special cased contacted_since and contacted_by
            # these two fields are together, if we have another case like this
            # we should probably formalize this
            if item == "contacted_since":
                contacted_by = request.GET.get('%s_contacted_by' % include_group[0])
                if contacted_by:
                    extra_data['contacted_by'] = contacted_by

            make_query_fn = query_data.get('query_fn', make_default_user_query)
            query, __human_query = make_query_fn(query_data, possible_values, item, extra_data)

            users = users.filter(**query)
            _human_query.append(__human_query)

        if not _human_query or (
            users.query.sql_with_params() == base_user_query.query.sql_with_params()):
            continue

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

    if users.query.sql_with_params() == base_user_query.query.sql_with_params():
        users = base_user_query.none()

    ctx['human_query'] = human_query
    ctx['users'] = users
    ctx['request'] = request
    request.session['akcrm.query'] = request.GET.urlencode()
    return ctx

@allow_http("GET")
@rendered_with("detail.html")
def detail(request, user_id):
    ctx = _detail(request, user_id)
    ctx['ACTIONKIT_URL'] = settings.ACTIONKIT_URL
    return ctx

@allow_http("GET")
def detail_json(request, user_id):
    ctx = _detail(request, user_id)
    def dthandler(obj):
        if isinstance(obj, datetime.datetime):
            return date(obj)
        elif hasattr(obj, 'to_json'):
            return obj.to_json()
    try:
        ctx['latest_action'] = ctx['actions'][0]
    except IndexError:
        ctx['latest_action'] = None
    try:
        ctx['latest_order'] = ctx['orders'][0]
    except IndexError:
        ctx['latest_order'] = None
    try:
        ctx['latest_open'] = ctx['opens'][0]
    except IndexError:
        ctx['latest_open'] = None
    try:
        ctx['latest_click'] = ctx['clicks'][0]
    except IndexError:
        ctx['latest_click'] = None

    agent = ctx['agent']
    ctx['sends'] = _mailing_history(request, agent).values()
    ctx['sends'] = sorted(ctx['sends'], key=itemgetter("mailed_at"), reverse=True)
    try:
        ctx['latest_send'] = ctx['sends'][0]
    except IndexError:
        ctx['latest_send'] = None    

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

    contact_history = list(ContactRecord.objects.filter(akid=user_id).order_by("-completed_at").select_related("user"))
    contact_form = ContactForm(initial={
            'akid': user_id,
            'user': request.user,
            })

    query = request.session.get('akcrm.query')

    _allowed_tags = AllowedTag.objects.all()
    allowed_tags = dict([(t.ak_tag_id, t) for t in _allowed_tags])
    _agent_tags = CoreTag.objects.using("ak").filter(
        corepagetag__page__coreaction__user=agent).values("name", "id", "corepagetag__page_id")

    agent_tags = []
    AgentTag = namedtuple("AgentTag", "name ak_tag_id editable allowed_tag_id")
    for tag in _agent_tags:
        editable = False
        allowed_tag_id = None
        if (tag['id'] in allowed_tags
            and allowed_tags[tag['id']].ak_page_id == tag['corepagetag__page_id']):
            editable = True
            allowed_tag_id = allowed_tags[tag['id']].id
        agent_tags.append(AgentTag(tag['name'], tag['id'], editable, allowed_tag_id))

    # The list of already-used tags may contain duplicates.
    # We need to filter out duplicates, and if there is an "editable" copy of the tag
    # as well as an "uneditable" copy, we need to discard the editable one.
    _agent_tags = {}
    for tag in agent_tags:
        _agent_tags.setdefault(tag.name, [])
        if tag.editable:
            _agent_tags[tag.name].append(tag)
        else:
            _agent_tags[tag.name].insert(0, tag)
    agent_tags = (copies[0] for copies in _agent_tags.values())

    # We also need to filter out the "special tag-page marker tag" 
    # from the list -- unless it too is editable!
    agent_tags = [tag for tag in agent_tags
                  if (tag.ak_tag_id != settings.AKTIVATOR_TAG_PAGE_TAG_ID
                      or tag.editable)]

    # Then, we need to filter out already-used tags from the list of addable tags.
    _agent_tags = [tag.name for tag in agent_tags]
    allowed_tags = [tag for tag in _allowed_tags if tag.tag_name not in _agent_tags]

    return locals()

@allow_http("POST")
def add_user_tag(request, user_id, tag_id):
    allowed_tag = get_object_or_404(AllowedTag, id=tag_id)
    action = rest.create_action(allowed_tag.ak_page_id, user_id)
    if request.is_ajax():
        return HttpResponse(action['action']['id'])
    return redirect("detail", user_id)

@allow_http("POST")
def remove_user_tag(request, user_id, tag_id):
    allowed_tag = get_object_or_404(AllowedTag, id=tag_id)
    action = get_object_or_404(CoreAction.objects.using("ak"),
                               page__id=allowed_tag.ak_page_id,
                               user__id=user_id)
    rest.delete_action(action.id)
    if request.is_ajax():
        return HttpResponse(action.id)
    return redirect("detail", user_id)

def _mailing_history(request, agent):
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
    
    return sends

@allow_http("GET")
def mailing_history(request, user_id):
    try:
        agent = CoreUser.objects.using("ak").get(id=user_id)
    except CoreUser.DoesNotExist:
        return HttpResponseNotFound("No such record exists")

    sends = _mailing_history(request, agent)

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
