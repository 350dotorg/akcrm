from actionkit import rest
from django.db import connections
from search.models import ActiveReport

def raw_sql_from_queryset(queryset):
    dummy_queryset = queryset.using('dummy')
    try:
        # trigger the query
        list(dummy_queryset)
    except:
        actual_sql = connections['dummy'].queries[-1]['sql']
        return actual_sql
    else:
        assert False, "Dummy query was expected to fail"

query_keys = [
    'phone',
    'campus',
    'id',
    'created_at',
    'updated_at',
    'email',
    'prefix',
    'first_name',
    'middle_name',
    'last_name',
    'suffix',
    'password',
    'subscription_status',
    'address1',
    'address2',
    'city',
    'state',
    'region',
    'postal',
    'zip',
    'plus4',
    'country',
    'source',
    'lang_id',
    'rand_id',
    ]

def result_to_model(result_spec):
    return dict(zip(query_keys, result_spec))

def report_or_query(raw_sql, human_query, query_string):
    slug = ActiveReport.slugify(query_string)
    try:
        report = ActiveReport.objects.get(slug=slug)
    except ActiveReport.DoesNotExist:
        return rest.query(raw_sql, human_query, query_string)
    else:
        return rest.poll_report(report.akid)
