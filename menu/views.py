# menu/views.py
from rest_framework.permissions import AllowAny
from rest_framework.generics import ListAPIView, RetrieveAPIView
from django.db.models import QuerySet
from .serializers import MenuItemSerializer

try:
    from .models import MenuItem  # your model
except Exception:
    from .models import Item as MenuItem  # fallback

def _qs() -> QuerySet:
    # Show everything so items you add in admin always appear.
    # (If you WANT availability gates, add them back later.)
    return MenuItem.objects.all().order_by("id")

class MenuItemListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = MenuItemSerializer
    def get_queryset(self): return _qs()

class MenuItemDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = MenuItemSerializer
    lookup_field = "pk"
    def get_queryset(self): return _qs()
