# menu/serializers.py
from rest_framework import serializers

class MenuItemSerializer(serializers.Serializer):
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
        for f in ("image", "photo", "thumbnail"):
            if hasattr(obj, f) and getattr(obj, f):
                try:
                    return getattr(obj, f).url
                except Exception:
                    return str(getattr(obj, f))
        return None

    def get_category(self, obj):
        for f in ("category", "menu_category", "group"):
            if hasattr(obj, f) and getattr(obj, f):
                c = getattr(obj, f)
                name = getattr(c, "name", None) or getattr(c, "title", None)
                return {"id": getattr(c, "id", None), "name": name}
        return None
