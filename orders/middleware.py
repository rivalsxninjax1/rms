# core/middleware.py
class EnsureCartInitializedMiddleware:
    """
    For anonymous users, make sure 'cart' exists and starts empty on first hit.
    This does NOT clear carts for returning guests unless you also clear on logout (we do).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if getattr(request, "user", None) and request.user.is_anonymous:
                if not request.session.get("_cart_init_done"):
                    request.session["cart"] = []
                    request.session["_cart_init_done"] = True
                    request.session.modified = True
        except Exception:
            pass
        return self.get_response(request)
