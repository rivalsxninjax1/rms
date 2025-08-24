# menu/urls.py
from django.urls import path
from .views import MenuItemListView, MenuItemDetailView

urlpatterns = [
    # Stable
    path("menu/items/", MenuItemListView.as_view(), name="menu-items"),
    path("menu/items/<int:pk>/", MenuItemDetailView.as_view(), name="menu-item-detail"),

    # Compatibility alias for older JS that might call /api/items/
    path("items/", MenuItemListView.as_view(), name="menu-items-compat"),
    path("items/<int:pk>/", MenuItemDetailView.as_view(), name="menu-item-detail-compat"),
]
