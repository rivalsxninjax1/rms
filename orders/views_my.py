# orders/views_my.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from .serializers import OrderListSerializer


class MyOrdersAPIView(APIView):
    """
    Return the authenticated user's orders.
    Paid history is visible via nested `payment.is_paid` and `invoice_url`.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        qs = (
            Order.objects.filter(created_by=request.user)
            .select_related("payment")    # OneToOne, if payments app enabled
            .order_by("-created_at")
        )
        data = OrderListSerializer(qs, many=True, context={"request": request}).data
        return Response(data)
