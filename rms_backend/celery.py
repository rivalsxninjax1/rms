import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')

app = Celery('rms_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()