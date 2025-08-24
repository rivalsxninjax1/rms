from django.urls import path
from . import views

app_name = "storefront"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("branches/", views.branches, name="branches"),
    path("menu/", views.menu, name="menu"),
    path("menu/<int:item_id>/", views.menu_item, name="menu-item"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.orders, name="orders"),
    path("contact/", views.contact, name="contact"),
    path("login/", views.login_page, name="login"),
    path("reservations/", views.reservations, name="reservations"),
]
