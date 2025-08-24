# payments/views.py
import json
import logging

import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from payments.services import (
    create_checkout_session,
    generate_order_invoice_pdf,
    mark_paid,
)

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


@csrf_exempt
def create_checkout_session_view(request, order_id: int):
    """
    POST -> returns {"url": "..."} for Stripe Checkout redirect (used by cart-pay.js)
    GET  -> convenience redirect to Stripe (302) if someone hits it directly.
    """
    order = get_object_or_404(Order, id=order_id)

    if request.method == "GET":
        session = create_checkout_session(order)
        return HttpResponseRedirect(session.url)

    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        session = create_checkout_session(order)
        return JsonResponse({"url": session.url})
    except ValueError as e:
        logger.warning("Stripe session error: %s", e)
        return JsonResponse({"detail": str(e)}, status=400)
    except stripe.error.StripeError as e:
        logger.exception("Stripe error: %s", e)
        return JsonResponse({"detail": "Payment provider error"}, status=502)
    except Exception as e:
        logger.exception("Unknown error: %s", e)
        return JsonResponse({"detail": "Server error"}, status=500)


@csrf_exempt
def stripe_webhook(request):
    """
    Verify Stripe signature; mark order as paid on session completion.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    etype = event.get("type")
    data = event.get("data", {}).get("object", {})

    try:
        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            order_id = (data.get("metadata") or {}).get("order_id")
            payment_intent_id = data.get("payment_intent")
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    mark_paid(order, payment_intent_id)

                    # optionally generate + attach invoice if your Order has FileField invoice_pdf
                    filename, pdf_bytes = generate_order_invoice_pdf(order)
                    if filename and pdf_bytes and hasattr(order, "invoice_pdf"):
                        from django.core.files.base import ContentFile
                        order.invoice_pdf.save(filename, ContentFile(pdf_bytes), save=True)
                except Order.DoesNotExist:
                    logger.warning("Webhook for unknown order_id=%s", order_id)
    except Exception as e:
        logger.exception("Webhook processing failed: %s", e)

    return HttpResponse(status=200)


def checkout_success(request):
    """
    Payment success page. Clears server-side session cart.
    Expects ?order=<id>
    """
    oid = request.GET.get("order")
    order = None
    if oid:
        try:
            order = Order.objects.get(pk=oid)
        except Order.DoesNotExist:
            order = None

    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass

    return render(request, "payments/checkout_success.html", {"order": order})


def checkout_cancel(request):
    return render(request, "payments/checkout_cancel.html")
