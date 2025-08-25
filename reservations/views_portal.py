from __future__ import annotations
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Table, Reservation
from .serializers_portal import (
    TableStatusSerializer,
    CreateReservationSerializer,
    ReservationSerializer,
)

# derive “20-minute hold after checkout” from existing Orders/Payments
def _current_dinein_busy_map(now=None):
    from payments.models import Payment  # local import to avoid circulars
    now = now or timezone.now()
    win = now - timedelta(minutes=20)
    # Paid dine-in orders in the last 20 minutes
    qs = (
        Payment.objects
        .filter(is_paid=True, updated_at__gt=win,
                order__source="DINE_IN",
                order__table_number__isnull=False)
        .select_related("order")
    )
    busy = {}
    for p in qs:
        tnum = str(p.order.table_number)
        remaining = int((p.updated_at + timedelta(minutes=20) - now).total_seconds())
        busy[tnum] = max(0, remaining)
    return busy  # {table_number_str: seconds_remaining}

def _parse_dt(date_str: str, time_str: str) -> datetime:
    # naive local dt ok if your app already assumes local timezone
    return datetime.fromisoformat(f"{date_str}T{time_str}")

def _active_reservations(slot_dt: datetime):
    # Treat reservations within ±90 minutes of the requested slot as blocking,
    # excluding terminal states. Adjust statuses to match yours if needed.
    margin = timedelta(minutes=90)
    date = slot_dt.date()
    time = slot_dt.time()
    start = (datetime.combine(date, time) - margin).time()
    end   = (datetime.combine(date, time) + margin).time()
    return (
        Reservation.objects.filter(
            reservation_date=date,
            reservation_time__gte=start,
            reservation_time__lte=end,
        )
        .exclude(status__in=["CANCELLED","COMPLETED","NO_SHOW"])
        .select_related("table")
    )

@login_required(login_url="/")
def reserve_page(request):
    return render(request, "reservations/reserve.html", {})

class AvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date = request.query_params.get("date")
        time = request.query_params.get("time")
        if not date or not time:
            return Response({"detail": "date and time are required"}, status=400)

        try:
            slot_dt = _parse_dt(date, time)
        except ValueError:
            return Response({"detail": "Invalid date/time format."}, status=400)

        now = timezone.now()
        # Map: table_id -> Reservation
        res_map = {}
        for r in _active_reservations(slot_dt):
            res_map[r.table_id] = r

        busy_map = _current_dinein_busy_map(now)  # table_number -> seconds

        payload = []
        for t in Table.objects.filter(is_active=True):
            status = "available"
            hold_seconds = None
            res_id = None
            res_status = ""

            # Busy due to 20m dine-in turnover
            if str(t.table_number) in busy_map and busy_map[str(t.table_number)] > 0:
                status = "busy"
                hold_seconds = busy_map[str(t.table_number)]

            # Reserved in the requested slot
            if t.id in res_map:
                status = "reserved"
                res_id = res_map[t.id].id
                res_status = res_map[t.id].status

            payload.append({
                "id": t.id,
                "table_number": t.table_number,
                "capacity": t.capacity,
                "status": status,
                "hold_seconds": hold_seconds,
                "reservation_id": res_id,
                "reservation_status": res_status,
            })

        return Response(TableStatusSerializer(payload, many=True).data, status=200)

class CreateReservationView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        ser = CreateReservationSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        table = Table.objects.select_for_update().get(pk=ser.validated_data["table_id"])
        slot_dt = _parse_dt(
            ser.validated_data["date"].isoformat(),
            ser.validated_data["time"].isoformat(timespec="minutes"),
        )

        # deny if dine-in turnover busy
        busy_map = _current_dinein_busy_map()
        if str(table.table_number) in busy_map and busy_map[str(table.table_number)] > 0:
            return Response({"detail": "Table busy (turnover). Try later or another table."}, status=409)

        # deny if another reservation blocks this time
        if _active_reservations(slot_dt).filter(table=table).exists():
            return Response({"detail": "Table reserved at that time."}, status=409)

        reservation = ser.save()
        return Response(ReservationSerializer(reservation).data, status=201)
