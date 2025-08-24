from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from .models import Order, Ticket

class PricingService:
    @staticmethod
    def calculate_totals(order, discount_type=None, discount_value=None, tip_amount=None):
        """Calculate order totals with discounts, tax, and tip"""
        subtotal = sum(item.item_total for item in order.items.all())
        
        # Apply discount
        discount_amount = Decimal('0.00')
        if discount_type and discount_value:
            if discount_type == 'PERCENT':
                discount_amount = subtotal * (discount_value / 100)
            else:  # FIXED
                discount_amount = min(discount_value, subtotal)
        
        # Calculate tax on discounted amount
        taxable_amount = subtotal - discount_amount
        tax_amount = taxable_amount * (order.location.organization.tax_percent / 100)
        
        # Calculate total
        tip_amount = tip_amount or Decimal('0.00')
        total = subtotal - discount_amount + tax_amount + tip_amount
        
        return {
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'tax_amount': tax_amount,
            'tip_amount': tip_amount,
            'total': total
        }

class OrderService:
    @staticmethod
    @transaction.atomic
    def place_order(order):
        """Place an order and create KOT ticket"""
        if order.status != 'DRAFT':
            raise ValueError("Only draft orders can be placed")
        
        # Calculate totals
        totals = PricingService.calculate_totals(order)
        for key, value in totals.items():
            setattr(order, key, value)
        
        # Update status and timestamp
        order.status = 'PLACED'
        order.placed_at = timezone.now()
        order.save()
        
        # Create KOT ticket
        ticket_number = f"KOT-{order.id}-{timezone.now().strftime('%H%M%S')}"
        items_snapshot = []
        for item in order.items.all():
            items_snapshot.append({
                'name': item.menu_item_name,
                'quantity': item.quantity,
                'modifiers': item.modifiers,
                'notes': item.notes
            })
        
        Ticket.objects.create(
            order=order,
            ticket_number=ticket_number,
            items_snapshot=items_snapshot
        )
        
        return order

    @staticmethod
    @transaction.atomic
    def pay_order(order, payment_data):
        """Process payment for an order"""
        from billing.models import Payment, InvoiceSequence
        from billing.services import PaymentService
        
        # Apply discount and tip
        discount_type = payment_data.get('discount_type')
        discount_value = payment_data.get('discount_value')
        tip_amount = payment_data.get('tip_amount', Decimal('0.00'))
        
        # Recalculate totals
        totals = PricingService.calculate_totals(order, discount_type, discount_value, tip_amount)
        
        # Update order financial fields
        order.discount_type = discount_type or ''
        order.discount_value = discount_value or Decimal('0.00')
        order.discount_amount = totals['discount_amount']
        order.tax_amount = totals['tax_amount']
        order.tip_amount = totals['tip_amount']
        order.total = totals['total']
        
        # Process payments
        payments = payment_data.get('payments', [])
        total_payment_amount = Decimal('0.00')
        
        for payment_info in payments:
            payment = Payment.objects.create(
                order=order,
                method=payment_info['method'],
                amount=payment_info['amount'],
                reference=payment_info.get('reference', ''),
                created_by=payment_data.get('user')
            )
            total_payment_amount += payment.amount
        
        order.amount_paid = total_payment_amount
        
        # Close order if fully paid
        if order.is_paid:
            order.status = 'CLOSED'
            order.closed_at = timezone.now()
            
            # Assign invoice number
            sequence, created = InvoiceSequence.objects.get_or_create(
                location=order.location,
                defaults={'prefix': 'INV', 'next_number': 1, 'padding': 4}
            )
            
            invoice_no = f"{sequence.prefix}-{str(sequence.next_number).zfill(sequence.padding)}"
            order.invoice_no = invoice_no
            
            # Increment sequence
            sequence.next_number += 1
            sequence.save()
        
        order.save()
        return order