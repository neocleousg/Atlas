from django.conf import settings


def atlas(request):
    return {"DEMO_MODE": getattr(settings, "DEMO_MODE", False)}
