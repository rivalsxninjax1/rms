from django.contrib.auth.models import AbstractUser
class User(AbstractUser):
    """Thin custom user; DO NOT redeclare groups/permissions."""
    pass
