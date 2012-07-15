from StringIO import StringIO
from actionkit import Client
from actionkit.models import *
from actionkit import rest
from akcrm.search.models import SearchQuery
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db import connections
from django.db.models import Count
from django.db.models import Sum
from djangohelpers import rendered_with, allow_http
from djangohelpers.templatetags.helpful_tags import qsify
from django.http import HttpResponseNotFound, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import date
from django.utils.simplejson import JSONEncoder
import csv
import datetime
import dateutil.parser
import json
import os.path
import re
from operator import itemgetter

from akcrm.cms.models import AllowedTag
from akcrm.crm.forms import ContactForm
from akcrm.crm.forms import SearchSaveForm
from akcrm.crm.models import ContactRecord
from akcrm.cms.models import HomePageHtml
from akcrm.permissions import authorize
from akcrm.search.models import AgentTag
from akcrm.search.utils import clamp
from akcrm.search.utils import latlon_bbox
from akcrm.search.utils import zipcode_to_latlon

def make_default_user_query(users, query_data, values, search_on, extra_data={}):
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


    if extra_data.get('istoggle', True):
        users = users.filter(**query)
        human_query = "%s is in %s" % (search_on, values)
    else:
        users = users.exclude(**query)
        human_query = "%s is not in %s" % (search_on, values)
    return users, human_query

def make_date_query(users, query_data, values, search_on, extra_data={}):
    date = values[0]
    match = dateutil.parser.parse(date)
    if extra_data.get('istoggle', True):
        users = users.filter(**{query_data['query']: match})
        human_query = "%s is in %s" % (search_on, values)
    else:
        users = users.exclude(**{query_data['query']: match})
        human_query = "%s is not in %s" % (search_on, values)
    return users, human_query

def make_zip_radius_query(users, query_data, values, search_on, extra_data={}):
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
        if extra_data.get('istoggle', True):
            users = users.filter(location__latitude__range=(lat1, lat2),
                                 location__longitude__range=(lon1, lon2))
            human_query = "within %s miles of %s" % (distance, zipcode)
        else:
            users = users.exclude(location__latitude__range=(lat1, lat2),
                                  location__longitude__range=(lon1, lon2))
            human_query = "not within %s miles of %s" % (distance, zipcode)
    else:
        if extra_data.get('istoggle', True):
            users = users.filter(zip=zipcode)
            human_query = "in zip code %s" % zipcode
        else:
            users = users.exclude(zip=zipcode)
            human_query = "not in zip code %s" % zipcode
    return users, human_query

def make_contact_history_query(users, query_data, values, search_on, extra_data={}):
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
    if extra_data.get('istoggle', True):
        users = users.filter(id__in=akids)
        human_query = " ".join(human_query)
    else:
        users = users.exclude(id__in=akids)
        human_query = 'not %s' % (" ".join(human_query))
    return users, human_query

def make_emails_opened_query(users, query_data, values, search_on, extra_data={}):
    num_opens = values[0]
    num_opens = int(num_opens)
    human_query = "opened at least %s emails" % num_opens
    if 'since' in extra_data:
        since = dateutil.parser.parse(extra_data['since'])
        users = users.filter(email_opens__created_at__gte=since)
        human_query += " since %s" % since
    users = users.annotate(num_opens=Count('email_opens', distinct=True))
    if extra_data.get('istoggle', True):
        users = users.filter(num_opens__gte=num_opens)
    else:
        users = users.exclude(num_opens__gte=num_opens)
        human_query = 'not %s' % human_query
    return users, human_query


def make_more_actions_since_query(users, query_data, values, search_on, extra_data={}):
    num_actions = values[0]
    num_actions = int(num_actions)
    human_query = 'more than %s actions' % num_actions
    if 'since' in extra_data:
        since = dateutil.parser.parse(extra_data['since'])
        users = users.filter(actions__created_at__gte=since)
        human_query += ' since %s' % extra_data['since']
    users = users.annotate(num_actions=Count('actions', distinct=True))
    if extra_data.get('istoggle', True):
        users = users.filter(num_actions__gt=num_actions)
    else:
        users = users.exclude(num_actions__gt=num_actions)
        human_query = 'not %s' % human_query
    return users, human_query


def make_donated_more_than_query(users, query_data, values, search_on, extra_data={}):
    if extra_data.get('istoggle', True):
        human_query = 'has donated more than %s' % values[0]
    else:
        human_query = 'has not donated more than %s' % values[0]
    total_donated = float(values[0])
    if 'since' in extra_data:
        since = dateutil.parser.parse(extra_data['since'])
        users = users.filter(orders__created_at__gte=since)
        human_query += ' since %s' % extra_data['since']
    users = users.filter(orders__status='completed')
    users = users.annotate(total_orders=Sum('orders__total'))
    if extra_data.get('istoggle', True):
        users = users.filter(total_orders__gte=total_donated)
    else:
        users = users.exclude(total_orders__gte=total_donated)
    return users, human_query


def make_donated_times_query(users, query_data, values, search_on, extra_data={}):
    if extra_data.get('istoggle', True):
        human_query = 'has donated more than %s times' % values[0]
    else:
        human_query = 'has not donated more than %s times' % values[0]
    times_donated = int(values[0])
    if 'since' in extra_data:
        since = dateutil.parser.parse(extra_data['since'])
        users = users.filter(orders__created_at__gte=since)
        human_query += ' since %s' % extra_data['since']
    users = users.filter(orders__status='completed')
    users = users.annotate(n_orders=Count('orders', distinct=True))
    if extra_data.get('istoggle', True):
        users = users.filter(n_orders__gte=times_donated)
    else:
        users = users.exclude(n_orders__gte=times_donated)
    return users, human_query


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
    'emails_opened': {
        'query_fn': make_emails_opened_query,
        },
    'more_actions': {
        'query_fn': make_more_actions_since_query,
        },
    'donated_more': {
        'query_fn': make_donated_more_than_query,
        },
    'donated_times': {
        'query_fn': make_donated_times_query,
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

    homepagehtml = None
    for htmlobj in HomePageHtml.objects.all():
        html = htmlobj.html.strip()
        if html:
            homepagehtml = htmlobj.html
        break

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
             ('emails_opened', "Emails Opened"),
             ('more_actions', "More Actions Since"),
             ('donated_more', "Donated Amount More Than"),
             ('donated_times', "Donated Times More Than"),
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
    if request.GET.get("count_submit"):
        resp = redirect("search_count")
        resp['Location'] += "%s" % qsify(request.GET)
        return resp
    ctx = _search(request)
    users = ctx['users']

    return ctx

@allow_http("GET")
@rendered_with("search_count.html")
def search_count(request):
    ctx = _search(request)
    users = ctx.pop('users')
    num_users = users.count()
    ctx['num_users'] = num_users
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
        if (include_pattern.match(key)
            and request.GET[key]
            and (not request.GET[key].endswith('_istoggle'))):
            includes.append((key, request.GET.getlist(key)))

    human_query = []

    all_user_queries = []
    for include_group in includes:
        users = base_user_query
        _human_query = []
        for item in include_group[1]:
            ## "distance" is handled in a group with "zipcode", so we ignore it here
            if item == "zipcode__distance":
                continue
            ## same for "contacted_by", in a group with "contacted_since"
            if item == "contacted_since__contacted_by":
                continue
            ## ditto
            if item == 'more_actions__since':
                continue

            possible_values = request.GET.getlist(
                "%s_%s" % (include_group[0], item))
            if len(possible_values) == 0:
                continue
            query_data = QUERIES[item]
            extra_data = {}

            istogglename = '%s_%s_istoggle' % (include_group[0], item)
            istoggle = request.GET.get(istogglename, '1')
            try:
                istoggle = bool(int(istoggle))
            except ValueError:
                istoggle = True
            extra_data['istoggle'] = istoggle

            ## XXX special cased zip code and distance
            # these two fields are together, if we have another case like this
            # we should probably formalize this
            if item == "zipcode":
                distance = request.GET.get('%s_zipcode__distance' % include_group[0])
                if distance:
                    extra_data['distance'] = distance

            ## XXX special cased contacted_since and contacted_by
            # these two fields are together, if we have another case like this
            # we should probably formalize this
            if item == "contacted_since":
                contacted_by = request.GET.get('%s_contacted_since__contacted_by' % include_group[0])
                if contacted_by:
                    extra_data['contacted_by'] = contacted_by

            if item == "emails_opened":
                since = request.GET.get('%s_emails_opened__since' % include_group[0])
                if since:
                    extra_data['since'] = since
            if item == "more_actions":
                since = request.GET.get('%s_more_actions__since' % include_group[0])
                if since:
                    extra_data['since'] = since
            if item == "donated_more":
                since = request.GET.get('%s_donated_more__since' % include_group[0])
                if since:
                    extra_data['since'] = since
            if item == "donated_times":
                since = request.GET.get('%s_donated_times__since' % include_group[0])
                if since:
                    extra_data['since'] = since

            make_query_fn = query_data.get('query_fn', make_default_user_query)
            users, __human_query = make_query_fn(users, query_data, possible_values, item, extra_data)
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
    num_results = len(users)

    log = open("/tmp/aktivator.log", 'a')
    print >> log, "%s | %s | %s | %s | %s | %s" % (
        datetime.datetime.now(),
        request.user.username,
        request.GET.urlencode(),
        users.query.sql_with_params(),
        num_results,
        connections['ak'].queries)
    log.close()

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
    
    total_donations = sum(order.total for order in orders)

    clicks = clicks_by_user(agent)
    opens = opens_by_user(agent)
    sends = CoreUserMailing.objects.using("ak").filter(user=agent).order_by("-created_at").select_related("subject")

    contact_history = list(ContactRecord.objects.filter(akid=user_id).order_by("-completed_at").select_related("user"))

    if getattr(request.PERMISSIONS, 'add_contact_record'):
        contact_form = ContactForm(initial={
                'akid': user_id,
                'user': request.user,
                })

    query = request.session.get('akcrm.query')

    _allowed_tags = AllowedTag.objects.all()
    allowed_tags = dict([(t.ak_tag_id, t) for t in _allowed_tags])
    _agent_tags = CoreTag.objects.using("ak").filter(
        pagetags__page__coreaction__user=agent).values("name", "id", "pagetags__page_id")

    agent_tags = []
    
    for tag in _agent_tags:
        editable = False
        allowed_tag_id = None
        if (tag['id'] in allowed_tags
            and allowed_tags[tag['id']].ak_page_id == tag['pagetags__page_id']):
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

@authorize("edit_user")
@allow_http("POST")
def add_user_tag(request, user_id, tag_id):
    allowed_tag = get_object_or_404(AllowedTag, id=tag_id)
    action = rest.create_action(allowed_tag.ak_page_id, user_id)
    if request.is_ajax():
        return HttpResponse(action['action']['id'])
    return redirect("detail", user_id)

def remove_user_tag(request, user_id, tag_id):
    ## disambiguate and redirect
    pass

@authorize("unrestricted_detag")
@allow_http("GET", "POST")
@rendered_with("remove_user_tags.html")
def remove_user_tag_unsafe(request, user_id, tag_id):
    tag = get_object_or_404(CoreTag.objects.using("ak"), id=tag_id)
    user = get_object_or_404(CoreUser.objects.using("ak"), id=user_id)
    affected_actions = CoreAction.objects.using("ak").filter(
        page__pagetags__tag__id=tag_id, user__id=user_id).select_related("page")
    if request.method == "GET":

        ## check whether any OTHER tags will be removed from the user as a consequence
        affected_actions_page_ids = [action.page.id for action in affected_actions]
        affected_actions_tags = CoreTag.objects.using("ak").filter(
            pagetags__page__id__in=affected_actions_page_ids)
        orphaned_tags = set()
        for tag in affected_actions_tags:
            other_actions = CoreAction.objects.using("ak").filter(
                page__pagetags__tag__id=tag.id, user__id=user_id).exclude(
                page__id__in=affected_actions_page_ids).exists()
            if not other_actions:
                orphaned_tags.add(tag)
        return locals()

    are_you_sure = request.POST.get("are_you_sure")
    if not are_you_sure:
        return redirect(".")
    try:
        are_you_sure = int(are_you_sure)
    except ValueError:
        return redirect(".")        
    affected_actions = list(affected_actions)
    if are_you_sure != len(affected_actions):
        return redirect(".")

    for action in affected_actions:
        rest.delete_action(action.id)

    return redirect("detail", user_id)
        

@authorize("edit_user")
@allow_http("POST")
def remove_user_tag_safe(request, user_id, tag_id):    
    allowed_tag = get_object_or_404(AllowedTag, ak_tag_id=tag_id)
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

@authorize("edit_user")
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


def safe_encode(value):
    if isinstance(value, unicode):
        return value.encode('utf-8')
    return str(value)


def user_to_csv_row(user, fields):
    row = []
    for field in fields:
        value = getattr(user, field, '')
        # phone is only callable field so far
        if callable(value):
            value = value()
        value = safe_encode(value)
        row.append(value)
    return row


@authorize("search_export")
@allow_http("GET")
@rendered_with("search_csv.html")
def search_csv(request):
    user_fields = ['first_name', 'last_name', 'email',
                   'address1', 'address2', 'city', 'state', 'region',
                   'postal', 'zip', 'country',
                   'source', 'subscription_status', 'phone']
    fields = request.GET.getlist('fields')
    if not fields:
        return dict(fields=user_fields,
                    request=request)
    
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(fields)
    users = _search(request)['users']
    for user in users:
        row = user_to_csv_row(user, fields)
        writer.writerow(row)
    response = HttpResponse(buffer.getvalue())
    response['Content-Type'] = 'text/csv'
    response['Content-Disposition'] = 'attachment; filename=search.csv'
    return response


@authorize("search_save")
@login_required
@rendered_with("search_save.html")
def search_save(request):
    if request.method == 'POST':
        form = SearchSaveForm(request.POST)
        if form.is_valid():
            searchquery = SearchQuery(
                slug=form.cleaned_data['slug'],
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                querystring=form.cleaned_data['querystring'],
                )
            searchquery.save()
            # need to save first to get primary key for relationship
            searchquery.user = request.user,
            searchquery.save()

            # add flash message
            url = '%s?%s' % (reverse('search'), searchquery.querystring)
            return HttpResponseRedirect(url)
    else:
        form = SearchSaveForm()

    querystring = request.META['QUERY_STRING']
    return dict(form=form, querystring=querystring)
