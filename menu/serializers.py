# menu/serializers.py
from rest_framework import serializers

def _abs_url(request, url: str | None) -> str | None:
    """Return an absolute URL if a request is available."""
    if not url:
        return None
    if request is None:
        return url
    try:
        return request.build_absolute_uri(url)
    except Exception:
        return url


class MenuItemSerializer(serializers.Serializer):
    """
    Robust serializer that doesn't assume model field names.
    It exposes:
      - id
      - name
      - description
      - price
      - image (absolute URL if possible)
      - category: {id, name}
    """
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    def get_name(self, obj):
        for f in ("name", "title"):
            if hasattr(obj, f) and getattr(obj, f):
                return getattr(obj, f)
        return f"Item {getattr(obj, 'id', '')}"

    def get_description(self, obj):
        for f in ("description", "details", "summary"):
            if hasattr(obj, f):
                return getattr(obj, f) or ""
        return ""

    def get_price(self, obj):
        for f in ("price", "unit_price", "selling_price", "amount"):
            if hasattr(obj, f):
                v = getattr(obj, f)
                return v if v is not None else 0
        return 0

    def get_image(self, obj):
        """
        Return absolute URL for image if request is in serializer context.
        Looks for common image field names.
        """
        request = self.context.get("request")
        for f in ("image", "photo", "thumbnail"):
            if hasattr(obj, f) and getattr(obj, f):
                try:
                    return _abs_url(request, getattr(obj, f).url)
                except Exception:
                    return _abs_url(request, str(getattr(obj, f)))
        return None

    def get_category(self, obj):
        """
        Return minimal category info without assuming exact field names.
        """
        for f in ("category", "menu_category", "group"):
            if hasattr(obj, f) and getattr(obj, f):
                c = getattr(obj, f)
                name = getattr(c, "name", None) or getattr(c, "title", None)
                return {"id": getattr(c, "id", None), "name": name}
        return None
