# payments/views.py
import json
import logging

import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from orders.models import Order
from payments.services import (
    create_checkout_session,
    mark_paid,
    save_invoice_pdf_file,
)

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


@login_required(login_url="/")
def create_checkout_session_view(request, order_id: int):
    """
    POST -> returns {"url": "..."} for Stripe Checkout redirect
    GET  -> 302 to Stripe (fallback/manual)
    Accepts optional JSON body: {"coupon": "PHRASE"} to attach to order.
    """
    order = get_object_or_404(Order, id=order_id)

    if request.method == "GET":
        session = create_checkout_session(order)
        return HttpResponseRedirect(session.url)

    if request.method != "POST":
        return HttpResponse(status=405)

    # Optional: coupon attach
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    coupon_code = (payload.get("coupon") or "").strip()

    if coupon_code:
        try:
            from coupons.services import apply_coupon_code_to_order
            ok, _msg = apply_coupon_code_to_order(order, coupon_code)
            if not ok:
                logger.info("Coupon rejected for order %s", order_id)
        except Exception as e:
            logger.info("Coupon apply failed: %s", e)

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
                    save_invoice_pdf_file(order)  # idempotent
                except Order.DoesNotExist:
                    logger.warning("Webhook for unknown order_id=%s", order_id)
    except Exception as e:
        logger.exception("Webhook processing failed: %s", e)

    return HttpResponse(status=200)


def checkout_success(request):
    oid = request.GET.get("order")
    session_id = request.GET.get("session_id")
    order = None
    invoice_url = None

    if session_id and getattr(settings, "STRIPE_SECRET_KEY", ""):
        try:
            sess = stripe.checkout.Session.retrieve(session_id)
            order_id = (sess.get("metadata") or {}).get("order_id") or oid
            if order_id:
                order = Order.objects.filter(pk=order_id).first()
            if order and (sess.get("payment_status") == "paid"):
                mark_paid(order, sess.get("payment_intent"))
        except Exception as e:
            logger.info("Could not verify session %s: %s", session_id, e)

    if order is None and oid:
        try:
            order = Order.objects.get(pk=oid)
        except Order.DoesNotExist:
            order = None

    if order:
        try:
            if not getattr(order, "invoice_pdf", None) or not order.invoice_pdf:
                save_invoice_pdf_file(order)
            if getattr(order, "invoice_pdf", None) and order.invoice_pdf:
                invoice_url = order.invoice_pdf.url
        except Exception:
            pass

    # clear server-side session cart
    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass

    return render(
        request,
        "payments/checkout_success.html",
        {"order": order, "invoice_url": invoice_url},
    )


def checkout_cancel(request):
    return render(request, "payments/checkout_cancel.html")
