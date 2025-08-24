
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Organization, Location
from menu.models import MenuCategory, MenuItem

class Command(BaseCommand):
    help = "Seed demo org, location, categories and menu items"

    def handle(self, *args, **opts):
        User = get_user_model()
        if not User.objects.filter(username="demo").exists():
            User.objects.create_user(username="demo", password="demo12345", email="demo@example.com")

        org, _ = Organization.objects.get_or_create(name="Karma & Kocktails", defaults={"tax_percent": 13})
        loc, _ = Location.objects.get_or_create(organization=org, name="Thamel", defaults={"timezone":"Asia/Kathmandu"})
        cat1, _ = MenuCategory.objects.get_or_create(organization=org, name="Starters")
        cat2, _ = MenuCategory.objects.get_or_create(organization=org, name="Mains")

        MenuItem.objects.get_or_create(category=cat1, name="Plain Lassi", defaults={"price": "3.50"})
        MenuItem.objects.get_or_create(category=cat1, name="Shrimp Chowmein", defaults={"price": "8.99"})
        MenuItem.objects.get_or_create(category=cat2, name="Kadhai Paneer", defaults={"price": "10.99"})
        MenuItem.objects.get_or_create(category=cat2, name="Rogan Josh (Bone-in)", defaults={"price": "12.99"})

        self.stdout.write(self.style.SUCCESS("Seeded demo data. Login: demo / demo12345"))
