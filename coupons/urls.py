# coupons/urls.py
from django.urls import path
from .views import validate_coupon, apply_coupon_to_session, apply_coupon_to_order_view

urlpatterns = [
    path("validate/", validate_coupon, name="coupon_validate"),
    path("apply/", apply_coupon_to_session, name="coupon_apply_session"),
    path("apply-to-order/", apply_coupon_to_order_view, name="coupon_apply_order"),
]
