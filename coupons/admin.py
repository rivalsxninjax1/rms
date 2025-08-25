from __future__ import annotations
from django.contrib import admin
from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "percent", "active", "valid_from", "valid_to", "times_used", "max_uses", "created_at")
    list_filter = ("active", "valid_from", "valid_to")
    search_fields = ("code", "phrase")
    readonly_fields = ("times_used", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("code", "phrase", "percent", "active")}),
        ("Validity", {"fields": ("valid_from", "valid_to", "max_uses")}),
        ("Usage", {"fields": ("times_used",)}),
        ("Meta", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
