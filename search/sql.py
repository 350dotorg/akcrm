from actionkit import rest
import datetime
from django.db import connections
from search.models import ActiveReport

def raw_sql_from_queryset(queryset):
    dummy_queryset = queryset.using('dummy')
    try:
        # trigger the query
        list(dummy_queryset)
    except Exception, e:
        queries = connections['dummy'].queries
        actual_sql = queries[-1]['sql']
        return actual_sql
    else:
        assert False, "Dummy query was expected to fail"

def result_to_model(result_spec, model_class, columns):
    if not result_spec:
        return None
    spec = dict(zip(columns, [
                cell if cell != "None" else None for cell in result_spec]))
    return model_class(**spec)

def get_or_create_report(raw_sql, human_query, query_string):
    try:
        report = ActiveReport.objects.get(query_string=query_string)
    except ActiveReport.DoesNotExist:
        report = ActiveReport(query_string=query_string)
    
    if not report.slug:
        slug = ActiveReport.slugify(
            raw_sql + datetime.datetime.now().utcnow().isoformat())
        report.slug = slug
    else:
        slug = report.slug

    if report.queryreport_id is None or report.queryreport_shortname is None:
        ## Create a new report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#creating-reports)
        ## using the raw sql
        resp = rest.create_report(raw_sql, human_query, slug, slug)
        report.queryreport_id = resp['id']
        queryreport_shortname = report.queryreport_shortname = resp['short_name']
    else:
        queryreport_shortname = report.queryreport_shortname

    if report.akid is None:
        ## and then trigger an asynchronous run of that report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#running-reports-asynchronously)
        handle = rest.run_report(queryreport_shortname)
        
        report.akid = handle

    if report.local_table is None:
        report.local_table = report.slug

    report.save()

    return report

from search.models import make_temporary_model
from django.core.management.color import no_style
def create_model(ModelClass):
    sqls, __ = connections['dummy'].creation.sql_create_model(ModelClass, no_style())

    cursor = connections['dummy'].cursor()
    for sql in sqls:
        # @@TODO
        try:
            cursor.execute(sql)
        except Exception, e:
            pass
    return ModelClass
