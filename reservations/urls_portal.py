from django.urls import path
from .views_portal import reserve_page, AvailabilityView, CreateReservationView

app_name = "reservations_portal"

urlpatterns = [
    path("", reserve_page, name="page"),
    path("api/availability/", AvailabilityView.as_view(), name="availability"),
    path("api/reservations/", CreateReservationView.as_view(), name="create"),
]
