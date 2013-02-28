from django.conf import settings
import json
import requests
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

def query(query, timeout=10):
    host = settings.ACTIONKIT_API_HOST
    if not host.startswith("https"):
        host = "https://" + host

    url = "%s/rest/v1/report/run/sql/" % host
    data = json.dumps(dict(query=query))
    resp = requests.post(url,
        auth=HTTPBasicAuth(
            settings.ACTIONKIT_API_USER, settings.ACTIONKIT_API_PASSWORD),
        headers={'content-type': 'application/json'},
        timeout=timeout,
        data=data)
    return resp
