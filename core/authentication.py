# core/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class LenientJWTAuthentication(JWTAuthentication):
    """
    Same as JWTAuthentication, but NEVER raises AuthenticationFailed.
    If the token is missing/invalid/user not found, it just returns None,
    letting the view proceed as AnonymousUser (when allowed).
    """
    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            # swallow "User not found", "No active account", etc.
            return None
        except Exception:
            # Any unexpected decode error -> treat as anonymous
            return None
