from django.conf import settings
import csv
import json
import requests
import requests.exceptions
from requests.auth import HTTPBasicAuth

from actionkit.utils import get_client
from actionkit.models import CorePage

def delete_action(action_id):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    url = "%s/rest/v1/action/%s" % (host, action_id)
    resp = requests.delete(url, auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD))
    assert resp.status_code == 204

def create_action(page_id, user_id):
    page_name = CorePage.objects.using("ak").get(id=page_id).name

    actionkit = get_client()
    return actionkit.act({'page': page_name, 'id': user_id})

class QueryError(Exception):
    def __init__(self, sql, message, human_query, query_string):
        self.sql = sql
        self.message = message
        self.human_query = human_query
        self.query_string = query_string

def query(query, human_query, query_string, timeout=10):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    url = "%s/rest/v1/report/run/sql/" % host
    data = json.dumps(dict(query=query))
    try:
        resp = requests.post(url,
                             auth=HTTPBasicAuth(
                settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD),
                             headers={'content-type': 'application/json'},
                             timeout=timeout,
                             data=data)
    except (requests.exceptions.Timeout, requests.exceptions.SSLError):
        raise QueryError(query, "The query took too long to run.",
                         human_query, query_string)
    if resp.status_code == 400:
        raise QueryError(query, "The query was too large, and Actionkit refused to run it.",
                         human_query, query_string)
    return json.loads(resp.content)

def create_report(sql, description, name, short_name):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    data = json.dumps(dict(sql=sql, description=description, 
                           name=name, short_name=short_name,
                           hidden=False))

    url = "%s/rest/v1/queryreport/" % host
    resp = requests.post(url, auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD),
                         headers={'content-type': 'application/json'},
                         data=data)
    assert resp.status_code == 201
    location = resp.headers['Location']
    return {"id": location.strip("/").split("/")[-1], "short_name": short_name}

def unhide_report(report_id):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    from actionkit.models import QueryReport
    report = QueryReport.objects.using("ak").select_related("report_ptr").get(
        report_ptr__id=report_id)
    data = json.dumps(dict(hidden=False, 
                           sql=report.sql, name=report.report_ptr.name,
                           short_name=report.report_ptr.short_name))
    url = "%s/rest/v1/queryreport/%s/" % (host, report_id)

    resp = requests.put(url, auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD),
                        headers={'content-type': 'application/json'},
                        data=data)
    assert resp.status_code == 201

def delete_report(report_id):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    url = "%s/rest/v1/queryreport/%s/" % (host, report_id)
    resp = requests.delete(url, auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD))
    assert resp.status_code == 204

def run_report(name):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    url = "%s/rest/v1/report/background/%s/" % (host, name)
    resp = requests.post(url, auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD),
                         headers={'Accept': "text/csv"})

    assert resp.status_code == 201
    location = resp.headers['Location']
    return location.strip("/").split("/")[-1]

class ReportIncomplete(Exception):
    def __init__(self, data):
        self.data = data

class ReportFailed(Exception):
    def __init__(self, data):
        self.data = data

def poll_report(akid):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    url = "%s/rest/v1/backgroundtask/%s/" % (host, akid)
    resp = requests.get(url, auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD),
                        headers={'content-type': 'application/json'})

    assert resp.status_code == 200
    results = json.loads(resp.content)

    if not results['completed']:
        raise ReportIncomplete(results)
    if results['details']['status'] != "complete":
        raise ReportFailed(results)

    download = results['details']['download_uri']
    url = "%s%s" % (host, download)
    resp = requests.get(url, auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD),
                        prefetch=False)
    resp.encoding = "utf-8"

    lines = (line for line in resp.iter_lines(chunk_size=10))
    data = csv.reader(lines)

    columns = data.next()
    return columns, data


