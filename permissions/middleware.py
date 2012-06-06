from akcrm.permissions import LazyPermissions

class PermissionsMiddleware(object):
    def process_request(self, request):
        setattr(request, 'PERMISSIONS', LazyPermissions(request))
