from django.contrib import admin
from django import forms

from .models import MenuItem, MenuCategory


# --- Forms -------------------------------------------------------------------

class MenuItemAdminForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make absolutely sure the FK has a full, valid queryset
        self.fields["category"].queryset = MenuCategory.objects.all()


# --- Admins ------------------------------------------------------------------

@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("sort_order", "name")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    form = MenuItemAdminForm

    # Use autocomplete instead of raw_id to prevent invalid values
    autocomplete_fields = ("category",)

    list_display = (
        "id",
        "name",
        "price",
        "is_available",
        "category",
        "sort_order",
        "is_vegetarian",
        "created_at",
    )
    list_filter = ("is_available", "category", "is_vegetarian")
    search_fields = ("name", "description")
    list_select_related = ("category",)
    ordering = ("sort_order", "name")

    # Belt-and-suspenders: ensure admin widget uses a full queryset
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs.setdefault("queryset", MenuCategory.objects.all())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
