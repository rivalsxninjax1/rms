# orders/apps.py
from django.apps import AppConfig

class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        # load login/logout cart merge signals
        from . import signals_cart  # noqa
