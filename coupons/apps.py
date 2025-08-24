# coupons/apps.py
from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "coupons"
    verbose_name = "Promotions & Coupons"
