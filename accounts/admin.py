from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseAdmin):
    list_display = ("id", "username", "email", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
