from actionkit.rest import QueryError
from djangohelpers.lib import rendered_with

@rendered_with("search/middleware_error.html")
def middleware_error(request, message):
    return dict(message=message)

class HttpQueryErrorMiddleware(object):
    def process_exception(self, request, exc):
        if not isinstance(exc, QueryError):
            return None
        sql = exc.sql
        message = exc.message

        ## Create a new report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#creating-reports)
        ## using the raw sql

        ## and then trigger an asynchronous run of that report
        ## (https://roboticdogs.actionkit.com/docs/manual/api/rest/reports.html#running-reports-asynchronously)

        ## We'll then have a handle on the newly created report (its URL will be returned in the Location header of the API response)
        ## and also a handle on the run-of-the-report (in the location header of the second API call)
        ## and I guess we'll need to store both of those handles somewhere

        return middleware_error(request, message)

        
        
