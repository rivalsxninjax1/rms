from django.shortcuts import render

def _ctx(page=None, **kw):
    base = {"page": page or ""}
    base.update(kw)
    return base

def home(request):
    return render(request, "storefront/index.html", _ctx("home"))

def about(request):
    return render(request, "storefront/about.html", _ctx("about"))

def branches(request):
    return render(request, "storefront/branches.html", _ctx("branches"))

def menu(request):
    return render(request, "storefront/menu.html", _ctx("menu"))

def menu_item(request, item_id: int):
    return render(request, "storefront/menu_item.html", _ctx("menu_item", item_id=item_id))

def cart(request):
    return render(request, "storefront/cart.html", _ctx("cart"))

def checkout(request):
    return render(request, "storefront/checkout.html", _ctx("checkout"))

def orders(request):
    return render(request, "storefront/orders.html", _ctx("orders"))

def contact(request):
    return render(request, "storefront/contact.html", _ctx("contact"))

def login_page(request):
    return render(request, "storefront/login.html", _ctx("login"))

def reservations(request):
    return render(request, "storefront/reservations.html", _ctx("reservations"))
