from __future__ import annotations
from datetime import timedelta, datetime
from django.utils import timezone
from celery import shared_task
from .models import Reservation

@shared_task
def mark_no_show_reservations():
    """
    Mark CONFIRMED/PENDING reservations as NO_SHOW if now >= reservation datetime + 20 minutes,
    and they were never seated.
    """
    now = timezone.now()
    ids = []
    for r in Reservation.objects.exclude(status__in=["CANCELLED","COMPLETED","NO_SHOW","SEATED"]):
        dt = datetime.combine(r.reservation_date, r.reservation_time)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        if now >= dt + timedelta(minutes=20):
            ids.append(r.id)
    if ids:
        Reservation.objects.filter(id__in=ids).update(status="NO_SHOW")
