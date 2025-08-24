# accounts/views.py
from __future__ import annotations

from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializers import (
    RegisterSerializer,
    EmailOrUsernameTokenObtainPairSerializer,
)


class EmailOrUsernameTokenObtainPairView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailOrUsernameTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


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


@require_GET
def whoami(request):
    """
    Session-based check (NOT JWT). Used by the session bridge on the client.
    """
    user = request.user if request.user.is_authenticated else None
    return JsonResponse({
        "authenticated": bool(user),
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", "") or "",
        "email": getattr(user, "email", "") or "",
    })


@method_decorator(csrf_exempt, name="dispatch")
class SessionLoginFromJWT(APIView):
    """
    Create a Django session from a valid JWT in the Authorization header.
    Triggers user_logged_in -> cart merge via orders.signals.
    """
    permission_classes = [AllowAny]
    authentication_classes: list = []  # authenticate manually

    def post(self, request, *args, **kwargs):
        authenticator = JWTAuthentication()
        try:
            authenticated = authenticator.authenticate(request)
        except Exception:
            return JsonResponse({"ok": False, "detail": "Invalid token"}, status=401)

        if not authenticated:
            return JsonResponse({"ok": False, "detail": "No/invalid token"}, status=401)

        user, _token = authenticated
        if not user or not user.is_active:
            return JsonResponse({"ok": False, "detail": "User inactive or not found"}, status=401)

        # Important: use Django's default auth backend id
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
class SessionLogout(APIView):
    """
    Log out the Django session (front-end also clears JWT).
    DO NOT touch any cart/session keys here.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            logout(request)
        except Exception:
            pass
        return JsonResponse({"ok": True})
