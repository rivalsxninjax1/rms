from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
for m in apps.get_app_config("core").get_models():
    try: admin.site.register(m)
    except AlreadyRegistered: pass
