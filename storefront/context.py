from django.conf import settings
def site_context(request):
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "RMS Store"),
        "GA_MEASUREMENT_ID": getattr(settings, "GA_MEASUREMENT_ID", ""),
        "WHATSAPP_NUMBER": getattr(settings, "WHATSAPP_NUMBER", ""),
        "BRANCHES": getattr(settings, "BRANCHES", []),
        "DEFAULT_CURRENCY": getattr(settings, "DEFAULT_CURRENCY", "NPR"),
    }
