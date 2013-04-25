from django.conf import settings

def common_settings(request):
    return {
        "ACTIONKIT_URL": settings.ACTIONKIT_URL,
        }
