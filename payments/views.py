# payments/views.py
import json
import logging

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt

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
    GET  -> create session and 302 redirect to Stripe Checkout
    POST -> create session and return JSON {url: "..."} for SPA usage
    """
    order = get_object_or_404(Order, pk=order_id)

    if request.method == "GET":
        try:
            session = create_checkout_session(order)
            url = getattr(session, "url", None)
            if url:
                return HttpResponseRedirect(url)
            return HttpResponse("No checkout URL returned.", status=500)
        except Exception as e:
            logger.exception("Failed to create checkout session: %s", e)
            return HttpResponse("Failed to start checkout", status=400)

    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    # (Optional) If you attach coupons here, keep your existing logic.
    # e.g. payload.get("coupon")

    try:
        session = create_checkout_session(order)
        return JsonResponse({"url": getattr(session, "url", None)}, status=201)
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
    Handle Stripe webhooks.
    Make sure STRIPE_WEBHOOK_SECRET in .env has NO trailing spaces/newlines.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = (getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning("Invalid webhook signature or payload: %s", e)
        return HttpResponse(status=400)

    etype = event.get("type")
    data = event.get("data", {}).get("object", {}) or {}

    try:
        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            order_id = (data.get("metadata") or {}).get("order_id")
            payment_intent_id = data.get("payment_intent")
            session_id = data.get("id")

            if order_id:
                try:
                    order = Order.objects.get(pk=int(order_id))
                    mark_paid(order, payment_intent_id=payment_intent_id, session_id=session_id)
                    try:
                        save_invoice_pdf_file(order)  # idempotent
                    except Exception:
                        pass
                except Order.DoesNotExist:
                    logger.warning("Webhook for unknown order_id=%s", order_id)

        elif etype in ("checkout.session.async_payment_failed", "payment_intent.payment_failed"):
            # Optional: set FAILED, notify user, etc.
            pass

    except Exception as e:
        logger.exception("Webhook processing failed: %s", e)
        return HttpResponse(status=500)

    return HttpResponse(status=200)


def checkout_success(request):
    """
    Simple thank-you page. If session_id is present, we try to fetch & verify it.
    """
    oid = request.GET.get("order")
    session_id = request.GET.get("session_id")
    order = None
    invoice_url = None

    if oid:
        try:
            order = Order.objects.get(pk=int(oid))
        except Order.DoesNotExist:
            order = None

    # Optional: verify session status
    if session_id and stripe.api_key:
        try:
            sess = stripe.checkout.Session.retrieve(session_id)
            if sess and getattr(sess, "payment_status", "") == "paid" and order:
                mark_paid(order, getattr(sess, "payment_intent", None), getattr(sess, "id", None))
        except Exception:
            pass

    if order:
        try:
            if not getattr(order, "invoice_pdf", None) or not order.invoice_pdf:
                save_invoice_pdf_file(order)
            if getattr(order, "invoice_pdf", None) and order.invoice_pdf:
                invoice_url = order.invoice_pdf.url
        except Exception:
            pass

    # Clear server-side session cart (if used in your flow)
    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass

    return render(request, "payments/checkout_success.html", {"order": order, "invoice_url": invoice_url})


def checkout_cancel(request):
    return render(request, "payments/checkout_cancel.html")
