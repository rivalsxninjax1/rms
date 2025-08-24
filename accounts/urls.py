# accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import RegisterView, MeView, EmailOrUsernameTokenObtainPairView

urlpatterns = [
    # Clean/current
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", EmailOrUsernameTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("me/", MeView.as_view(), name="me"),

    # Back-compat for legacy JS
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/token/", EmailOrUsernameTokenObtainPairView.as_view(), name="auth_token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth_token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="auth_token_verify"),
]
