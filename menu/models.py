from django.conf import settings
from django.db import models

class MenuCategory(models.Model):
    organization = models.ForeignKey('core.Organization', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='menu_items/', null=True, blank=True)
    is_vegetarian = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    preparation_time = models.PositiveIntegerField(default=15, help_text="Minutes")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"

class ModifierGroup(models.Model):
    SELECTION_TYPE_CHOICES = [
        ('SINGLE', 'Single Selection'),
        ('MULTIPLE', 'Multiple Selection'),
    ]
    
    menu_items = models.ManyToManyField(MenuItem, related_name='modifier_groups')
    name = models.CharField(max_length=100)
    selection_type = models.CharField(max_length=10, choices=SELECTION_TYPE_CHOICES, default='SINGLE')
    min_selections = models.PositiveIntegerField(default=0)
    max_selections = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

class Modifier(models.Model):
    modifier_group = models.ForeignKey(ModifierGroup, on_delete=models.CASCADE, related_name='modifiers')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.modifier_group.name} - {self.name}"