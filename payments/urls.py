# payments/urls.py
from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("create-checkout-session/<int:order_id>/", views.create_checkout_session_view, name="create_checkout_session"),
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("success/", views.checkout_success, name="checkout_success"),
    path("cancel/", views.checkout_cancel, name="checkout_cancel"),
]
