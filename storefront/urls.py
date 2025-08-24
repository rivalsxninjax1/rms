# storefront/urls.py
from django.urls import path
from . import views
from .views import MenuItemsView, MyOrdersView

app_name = "storefront"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("branches/", views.branches, name="branches"),

    # /menu/ renders items + images + actions via MenuItemsView
    path("menu/", MenuItemsView.as_view(), name="menu"),
    path("menu/<int:item_id>/", views.menu_item, name="menu-item"),

    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),

    # Legacy orders page kept (unchanged)
    path("orders/", views.orders, name="orders"),

    # My Orders (paid history + invoice links + reorder)
    path("my-orders/", MyOrdersView.as_view(), name="my_orders"),

    path("contact/", views.contact, name="contact"),
    path("login/", views.login_page, name="login"),
    path("reservations/", views.reservations, name="reservations"),
]
