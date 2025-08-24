from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

# If you have a Coupon model, import and validate properly. For now, stub logic:
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def validate_coupon(request):
    code = (request.data or {}).get("code", "").strip().upper()
    if not code:
        return Response({"valid": False}, status=status.HTTP_200_OK)

    # TODO: integrate real promotions logic / Coupon model checks here.
    # For testing: "WELCOME10" => 10% off
    if code == "WELCOME10":
        return Response({"valid": True, "discount_percent": 10}, status=status.HTTP_200_OK)

    return Response({"valid": False}, status=status.HTTP_200_OK)
