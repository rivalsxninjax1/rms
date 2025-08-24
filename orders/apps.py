# orders/apps.py
from django.apps import AppConfig

class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        # Register signal handlers (cart merge on login)
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Keep the app boot resilient; log if you prefer
            pass
