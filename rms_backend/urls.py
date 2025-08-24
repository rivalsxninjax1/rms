# rms_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("coupons/", include("coupons.urls")),
    # APIs
    path("api/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("api/", include(("menu.urls", "menu"), namespace="menu")),
    path("api/orders/", include(("orders.urls", "orders"), namespace="orders")),

    # Payments
    path("payments/", include(("payments.urls", "payments"), namespace="payments")),

    # Storefront
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
