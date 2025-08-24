# core/middleware.py
from django.http import HttpResponsePermanentRedirect
from django.conf import settings

class CanonicalHostMiddleware:
    """
    Redirects all requests to settings.CANONICAL_HOST (no scheme).
    Enabled when CANONICAL_HOST is set and DEBUG=False.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.host = getattr(settings, "CANONICAL_HOST", "").strip()

    def __call__(self, request):
        if not self.host:
            return self.get_response(request)
        incoming = request.get_host()
        in_host = incoming.split(":")[0]
        if in_host.lower() != self.host.lower():
            return HttpResponsePermanentRedirect(f"https://{self.host}{request.get_full_path()}")
        return self.get_response(request)
