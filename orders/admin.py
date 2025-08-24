from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("menu_item",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "created_by", "customer_name", "customer_email", "status", "is_paid", "created_at")
    list_filter = ("status", "is_paid", "created_at")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]

    search_fields = ("=id", "customer_name", "customer_email", "created_by__username", "created_by__email")
    raw_id_fields = ("created_by", "location")
    list_select_related = ("created_by", "location")
    ordering = ("-created_at",)
