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
    'name',
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

def result_to_model(result_spec, model_class):
    if not result_spec:
        return None
    spec = dict(zip(query_keys, [
                cell if cell != "None" else None for cell in result_spec]))
    return model_class(**spec)

def get_or_create_report(raw_sql, human_query, query_string):
    try:
        report = ActiveReport.objects.get(query_string=query_string)
    except ActiveReport.DoesNotExist:
        slug = ActiveReport.slugify(query_string)

        ## Create a new report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#creating-reports)
        ## using the raw sql
        resp = rest.create_report(raw_sql, human_query, slug, slug)

        ## and then trigger an asynchronous run of that report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#running-reports-asynchronously)
        handle = rest.run_report(resp['short_name'])

        ## We'll then have a handle on the newly created report (its URL will be returned in the Location header of the API response)
        ## and also a handle on the run-of-the-report (in the location header of the second API call)
        ## and I guess we'll need to store both of those handles somewhere
        report = ActiveReport(query_string=query_string, akid=handle, slug=slug)
        report.save()

    return report

from search.models import make_temporary_model
from django.core.management.color import no_style
def create_model(query_string):
    slug = ActiveReport.slugify(query_string)

    ModelClass = make_temporary_model(slug)

    sqls, __ = connections['dummy'].creation.sql_create_model(ModelClass, no_style())

    cursor = connections['dummy'].cursor()
    for sql in sqls:
        try:
            cursor.execute(sql)
        except Exception:
            pass
    return ModelClass
