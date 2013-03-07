from actionkit import rest
from djangohelpers.lib import rendered_with
from akcrm.search.models import ActiveReport

@rendered_with("search/middleware_error.html")
def middleware_error(request, message):
    return dict(message=message)

class HttpQueryErrorMiddleware(object):
    def process_exception(self, request, exc):
        if not isinstance(exc, rest.QueryError):
            return None

        slug = ActiveReport.slugify(exc.query_string)

        ## Create a new report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#creating-reports)
        ## using the raw sql
        resp = rest.create_report(exc.sql, exc.human_query, slug, slug)

        ## and then trigger an asynchronous run of that report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#running-reports-asynchronously)
        handle = rest.run_report(resp['short_name'])

        ## We'll then have a handle on the newly created report (its URL will be returned in the Location header of the API response)
        ## and also a handle on the run-of-the-report (in the location header of the second API call)
        ## and I guess we'll need to store both of those handles somewhere
        ActiveReport(query_string=exc.query_string, akid=handle, slug=slug).save()

        return middleware_error(request, exc.message)

        
        
