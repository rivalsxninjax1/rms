# FILE: loyalty/services.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.db import transaction

from .models import LoyaltyConfig, LoyaltyProgress, LoyaltyReward


def add_tip_and_maybe_grant(user, tip_amount: Decimal):
    if not user or not user.is_authenticated:
        return
    cfg = LoyaltyConfig.get_solo()
    prog, _ = LoyaltyProgress.objects.get_or_create(user=user)
    prog.total_tip = (prog.total_tip or Decimal("0.00")) + (tip_amount or Decimal("0.00"))
    prog.save(update_fields=["total_tip"])
    if prog.total_tip >= cfg.threshold_tip_total:
        has_unredeemed = LoyaltyReward.objects.filter(user=user, is_redeemed=False).exists()
        if not has_unredeemed:
            LoyaltyReward.objects.create(
                user=user,
                reward_type=cfg.reward_type,
                reward_amount=cfg.reward_amount,
            )

def get_available_reward_for_user(user) -> Optional[LoyaltyReward]:
    if not user or not user.is_authenticated:
        return None
    return LoyaltyReward.objects.filter(user=user, is_redeemed=False, reserved_order_id__isnull=True).order_by("created_at").first()

@transaction.atomic
def reserve_reward_for_order(reward: LoyaltyReward, order):
    if reward.reserved_order_id:
        return
    reward.reserved_order_id = order.id
    reward.save(update_fields=["reserved_order_id"])

@transaction.atomic
def redeem_reserved_reward_if_any(order):
    if not (order and order.created_by_id):
        return
    reward = LoyaltyReward.objects.filter(user=order.created_by, reserved_order_id=order.id, is_redeemed=False).first()
    if not reward:
        return
    reward.is_redeemed = True
    reward.redeemed_at = timezone.now()
    reward.save(update_fields=["is_redeemed","redeemed_at"])
    try:
        prog = order.created_by.loyalty_progress
    except LoyaltyProgress.DoesNotExist:
        return
    prog.reset()
