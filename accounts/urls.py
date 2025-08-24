# accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    RegisterView, MeView, EmailOrUsernameTokenObtainPairView,
    whoami, SessionLoginFromJWT, SessionLogout
)

app_name = "accounts"

urlpatterns = [
    # Clean/current
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", EmailOrUsernameTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("me/", MeView.as_view(), name="me"),

    # Session bridge (client uses these)
    path("auth/whoami/", whoami, name="whoami"),
    path("auth/session/", SessionLoginFromJWT.as_view(), name="session_from_jwt"),
    path("auth/logout/", SessionLogout.as_view(), name="session_logout"),

    # New friendly auth endpoints for modal JS
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/login/", EmailOrUsernameTokenObtainPairView.as_view(), name="auth_login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="auth_verify"),

    # Back-compat for legacy JS (kept)
    path("auth/token/", EmailOrUsernameTokenObtainPairView.as_view(), name="auth_token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth_token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="auth_token_verify"),
]
