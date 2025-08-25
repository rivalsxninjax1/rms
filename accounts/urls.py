# accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView  # optional (kept if used elsewhere)

from .views import (
    whoami,
    SessionLogout,
    SessionLoginJSON,
    RegisterJSON,
    MeView,
)

app_name = "accounts"

urlpatterns = [
    # Session-based JSON endpoints for the modal (Django auth + CSRF)
    path("login/", SessionLoginJSON.as_view(), name="login_json"),
    path("register/", RegisterJSON.as_view(), name="register_json"),
    path("logout/", SessionLogout.as_view(), name="logout_json"),

    # Session check + profile
    path("auth/whoami/", whoami, name="whoami"),
    path("me/", MeView.as_view(), name="me"),

    # Optional: keep these if other parts of your stack still need them
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
]
