# accounts/views.py
from __future__ import annotations

import json
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.http import JsonResponse, HttpRequest
from django.views import View
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

User = get_user_model()

# --------- Helpers ---------
def _json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}

def _bad(msg="Invalid request", code=400):
    return JsonResponse({"ok": False, "detail": msg}, status=code)

# --------- Public (session) endpoints used by the modal ---------

@require_GET
def whoami(request):
    u = request.user if request.user.is_authenticated else None
    return JsonResponse({
        "authenticated": bool(u),
        "id": getattr(u, "id", None),
        "username": getattr(u, "username", "") or "",
        "email": getattr(u, "email", "") or "",
    })

@method_decorator(csrf_protect, name="dispatch")
class SessionLoginJSON(View):
    """
    POST /accounts/login/
    Body: { "username": "...", "password": "..." }
    Creates a Django session on success. Returns JSON.
    """
    def post(self, request: HttpRequest):
        data = _json_body(request)
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return _bad("Username and password required.", 400)

        # Allow email as login identifier
        user = authenticate(request, username=username, password=password)
        if not user and "@" in username:
            try:
                account = User.objects.get(email__iexact=username)
                user = authenticate(request, username=account.get_username(), password=password)
            except User.DoesNotExist:
                user = None

        if not user:
            return _bad("Invalid credentials.", 401)
        if not user.is_active:
            return _bad("User disabled.", 403)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return JsonResponse({"ok": True, "user": {"id": user.id, "username": user.get_username(), "email": user.email or ""}})

@method_decorator(csrf_protect, name="dispatch")
class RegisterJSON(View):
    """
    POST /accounts/register/
    Body: { "username": "...", "email": "...", "password": "...", "first_name"?, "last_name"? }
    Creates user, logs them in (session), returns JSON.
    """
    def post(self, request: HttpRequest):
        data = _json_body(request)
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()

        if not username or not password or not email:
            return _bad("username, email and password are required.", 400)
        if User.objects.filter(username__iexact=username).exists():
            return _bad("Username already taken.", 409)
        if User.objects.filter(email__iexact=email).exists():
            return _bad("Email already in use.", 409)

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
        except Exception:
            return _bad("Could not create user.", 400)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return JsonResponse({"ok": True, "user": {"id": user.id, "username": user.get_username(), "email": user.email or ""}})

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        u = request.user
        return Response({
            "id": u.id,
            "username": u.get_username(),
            "email": getattr(u, "email", "") or "",
            "first_name": getattr(u, "first_name", "") or "",
            "last_name": getattr(u, "last_name", "") or "",
        })

@method_decorator(csrf_protect, name="dispatch")
class SessionLogout(View):
    """
    POST /accounts/logout/
    Clears cart-related keys and logs the user out.
    """
    def post(self, request, *args, **kwargs):
        try:
            request.session.pop("cart", None)
            request.session.pop("cart_meta", None)
            request.session.pop("applied_coupon", None)
            request.session.modified = True
        except Exception:
            pass
        try:
            logout(request)
        except Exception:
            pass
        return JsonResponse({"ok": True})
