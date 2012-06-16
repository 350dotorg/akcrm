from StringIO import StringIO
from actionkit import Client
from actionkit.models import CoreAction
from actionkit.models import CoreLanguage
from actionkit.models import CorePage
from actionkit.models import CorePhone
from actionkit.models import CoreTag
from actionkit.models import CoreUser
from actionkit.models import CoreUserField
from actionkit.models import CoreUserMailing
from actionkit import rest
from django.conf import settings
from django.db import connections
from django.db.models import Count
from djangohelpers import rendered_with, allow_http
from django.http import HttpResponse
from django.http import HttpResponseNotFound
from django.http import HttpResponseRedirect
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
from akcrm.crm.models import ContactRecord
from akcrm.permissions import authorize
from akcrm.search.models import AgentTag
from akcrm.search.utils import clamp
from akcrm.search.utils import latlon_bbox
from akcrm.search.utils import zipcode_to_latlon
import akcrm.search.query as q


def in_(column):
    return lambda value, request: q.in_(column, value)


def action_page_id(value, request):
    specs = [q.in_('cp.id', value),
             q.join('core_action ca', 'ca.user_id=cu.id'),
             q.join('core_page cp', 'ca.page_id=cp.id')]
    return q.combine_specs(specs)


def action_page_pagetags_tag_in(value, request):
    specs = [q.in_('ct.id', value),
             q.join('core_action ca', 'ca.user_id=cu.id'),
             q.join('core_page cp', 'ca.page_id=cp.id'),
             q.join('core_page_tags cpt', 'cpt.page_id=cp.id'),
             q.join('core_tag ct', 'cpt.tag_id=ct.id')]
    return q.combine_specs(specs)


def userfield_vertical(name):
    def query(value, request):
        specs = [q.vertical('cuf.name', name, 'cuf.value', value),
                 q.join('core_userfield cuf', 'cu.id=cuf.parent_id')]
        return q.combine_specs(specs)
    return query


def language(value, request):
    specs = [q.in_('clang.id', value),
             q.join('core_language clang', 'cu.lang_id=clang.id')]
    return q.combine_specs(specs)


def created_at(date_comparison):
    def query(value, request):
        datespec = value[0]
        parsed_date = dateutil.parser.parse(datespec)
        return q.simple_filter(date_comparison, 'created_at', parsed_date)
    return query


def zip_radius(value, request):
    zipcode = value[0]
    zipcode = int(zipcode)
    err = "No distance found for zip query"
    assert 'include:0_distance' in request.GET, err
    distance_string = request.GET['include:0_distance']
    distance = float(distance_string)
    assert distance > 0, "Bad distance"
    latlon = zipcode_to_latlon(zipcode)
    assert latlon is not None, "No location found for: %s" % zipcode
    lat, lon = latlon
    bbox = latlon_bbox(lat, lon, distance)
    err = "Bad bounding box for latlon: %s,%s" % (lat, lon)
    assert bbox is not None, err
    lat1, lat2, lon1, lon2 = bbox
    specs = [
        q.between('cloc.latitude', lat1, lat2),
        q.between('cloc.longitude', lon1, lon2),
        q.join('core_location cloc', 'cu.id=cloc.user_id')]
    query = q.combine_filters_and(specs)
    return q.combine_specs(
        [query, q.human('%s miles from %s' % (distance_string, zipcode))])


def contact_history(value, request):
    contacted_since = value[0]
    match = dateutil.parser.parse(contacted_since)
    search = ContactRecord.objects.filter(completed_at__gt=match)
    contacted_by = request.GET.get('contacted_by')
    if contacted_by is not None:
        search = search.filter(user__username=contacted_by)
        human_query.append("by %s" % contacted_by)
    akids = list(search.values_list("akid", flat=True))
    if len(akids) == 0:
        ## TODO give a helpful error message, not a mysterious always-null query
        akids = [0]
    return q.in_('id', akids)


QUERIES = {
    'country': in_('cu.country'),
    'region': in_('cu.region'),
    'state': in_('cu.state'),
    'city': in_('cu.city'),
    'action': action_page_id,
    'source': in_('cu.source'),
    'tag': action_page_pagetags_tag_in,
    'organization': userfield_vertical('organization'),
    'skills': userfield_vertical('skills'),
    'engagement_level': userfield_vertical('engagement_level'),
    'language': language,
    'created_before': created_at('<='),
    'created_after': created_at('>='),
    'zipcode': zip_radius,
    'contacted_since': contact_history,
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
    includes = []

    include_pattern = re.compile("^include:\d+$")
    for key in request.GET.keys():
        if include_pattern.match(key) and request.GET[key]:
            includes.append((key, request.GET.getlist(key)))

    queries_to_or = []
    queries_to_and = []
    for include_group in includes:
        items = include_group[1]
        for item in items:
            possible_values = request.GET.getlist(
                "%s_%s" % (include_group[0], item))
            if len(possible_values) == 0:
                continue
            query_fn = QUERIES.get(item, None)
            if query_fn is None:
                continue
            query = query_fn(possible_values, request)
            queries_to_and.append(query)

        anded = q.combine_filters_and(queries_to_and)
        queries_to_or.append(anded)

    ored = q.combine_filters_or(queries_to_or)

    # additional and queries to add on
    additional_filters_to_and = []
    if request.GET.get("user_name"):
        query = q.like(
            "CONCAT(cu.first_name, ' ', cu.last_name)",
            "%" + "%".join(request.GET['user_name'].split()) + "%")
        additional_filters_to_and.append(query)

    if request.GET.get("user_email"):
        query = q.like('cu.email', request.GET['user_email'] + '%')
        additional_filters_to_and.append(query)

    additional_anded = q.combine_filters_and(additional_filters_to_and)
    all_combined = q.combine_filters_or([ored, additional_anded])

    sql, parameters = q.user_sql(all_combined)

    users = list(CoreUser.objects.db_manager('ak').raw(sql, parameters))

    #cursor = connections['ak'].cursor()
    #cursor.execute(sql, parameters)
    #results = cursor.fetchall()
    #users = [CoreUser(*result) for result in results]


#    user_ids = [u.id for u in users]
#    phones = CorePhone.objects.using('ak').filter(user_id__in=user_ids)
#    user_id_phones_map = {}
#    for phone in phones:
#        user_id_phones_map.setdefault(phone.user_id, []).append(phone)
#
#    userfields = CoreUserField.objects.using('ak').filter(
#        parent_id__in=user_ids)
#    user_id_fields_map = {}
#    for uf in userfields:
#        user_id_fields_map.setdefault(uf.parent_id, []).append(uf)
#
#    for user in users:
#        phones = user_id_phones_map.get(user.id)
#        if phones:
#            user.phones = phones
#        fields = user_id_fields_map.get(user.id)
#        if fields:
#            user.fields = fields


    ctx = dict(includes=includes,
               params=request.GET)

    ctx['human_query'] = all_combined['human']
    ctx['users'] = users
    ctx['request'] = request
    request.session['akcrm.query'] = request.GET.urlencode()
    num_results = len(users)

    log = open("/tmp/aktivator.log", 'a')
    print >> log, "%s | %s | %s | %s | %s | %s" % (
        datetime.datetime.now(),
        request.user.username,
        request.GET.urlencode(),
        sql,  # users.query.sql_with_params(),
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
        corepagetag__page__coreaction__user=agent).values("name", "id", "corepagetag__page_id")

    agent_tags = []
    
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

@authorize("edit_user")
@allow_http("POST")
def add_user_tag(request, user_id, tag_id):
    allowed_tag = get_object_or_404(AllowedTag, id=tag_id)
    action = rest.create_action(allowed_tag.ak_page_id, user_id)
    if request.is_ajax():
        return HttpResponse(action['action']['id'])
    return redirect("detail", user_id)

@authorize("edit_user")
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


def user_to_csv_row(user, fields):
    row = []
    for field in fields:
        value = getattr(user, field, '')
        row.append(value)
    return row


@authorize("search_export")
@allow_http("GET")
@rendered_with("search_csv.html")
def search_csv(request):
    user_fields = ['first_name', 'last_name', 'email',
                   'address1', 'address2', 'city', 'state', 'region',
                   'postal', 'zip', 'country',
                   'source', 'subscription_status']
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
