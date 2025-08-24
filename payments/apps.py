# FILE: payments/apps.py
from django.apps import AppConfig
class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        # Ensure signals are registered
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
