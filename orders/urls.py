# orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, SessionCartViewSet

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"cart", SessionCartViewSet, basename="session-cart")

urlpatterns = [
    path("", include(router.urls)),
    # explicit reset endpoint used by JS (keeps your old behavior)
    path("cart/reset_session/", SessionCartViewSet.as_view({"post": "reset_session"}), name="cart-reset"),
]
