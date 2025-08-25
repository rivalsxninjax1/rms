# rms_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # Coupons
    path("coupons/", include("coupons.urls")),

    # Normal session endpoints for login/register/logout/whoami
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts_session")),

    # APIs (unchanged)
    path("api/", include(("menu.urls", "menu"), namespace="menu")),
    path("api/orders/", include(("orders.urls", "orders"), namespace="orders")),

    # Payments
    path("payments/", include(("payments.urls", "payments"), namespace="payments")),
    path("reserve/", include("reservations.urls_portal", namespace="reservations_portal")),

    # Storefront pages
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
