from django.urls import path
from .views import validate_coupon

app_name = "promotions"

urlpatterns = [
    path("promotions/validate/", validate_coupon, name="validate"),
]
