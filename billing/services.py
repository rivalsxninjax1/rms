import os
import qrcode
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from .models import PaymentReceipt

class ReceiptService:
    @staticmethod
    def generate_receipt_pdf(order, user):
        """Generate PDF receipt for an order"""
        
        # Create filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"receipt_{order.invoice_no or order.id}_{timestamp}.pdf"
        filepath = os.path.join(settings.MEDIA_ROOT, 'receipts', filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(filepath, pagesize=A5, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=6
        )
        
        # Organization header
        org = order.location.organization
        story.append(Paragraph(org.name, title_style))
        if org.address:
            story.append(Paragraph(org.address, header_style))
        if org.phone:
            story.append(Paragraph(f"Phone: {org.phone}", header_style))
        
        story.append(Spacer(1, 12))
        
        # Receipt details
        receipt_data = [
            ['Receipt', ''],
            ['Invoice No:', order.invoice_no or f'ORD-{order.id}'],
            ['Date:', order.closed_at.strftime('%Y-%m-%d %H:%M') if order.closed_at else order.created_at.strftime('%Y-%m-%d %H:%M')],
            ['Table:', order.table_number or 'N/A'],
            ['Customer:', order.customer_name or 'Walk-in'],
        ]
        
        receipt_table = Table(receipt_data, colWidths=[2*inch, 2*inch])
        receipt_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(receipt_table)
        story.append(Spacer(1, 12))
        
        # Order items
        item_data = [['Item', 'Qty', 'Price', 'Total']]
        
        for item in order.items.all():
            modifiers_text = ''
            if item.modifiers:
                modifiers_text = ' + ' + ', '.join([mod['name'] for mod in item.modifiers])
            
            item_name = item.menu_item_name + modifiers_text
            item_data.append([
                item_name,
                str(item.quantity),
                f"₹{item.menu_item_price}",
                f"₹{item.item_total}"
            ])
        
        items_table = Table(item_data, colWidths=[2.5*inch, 0.5*inch, 0.7*inch, 0.7*inch])
        items_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ]))
        
        story.append(items_table)
        story.append(Spacer(1, 12))
        
        # Totals
        totals_data = [
            ['Subtotal:', f"₹{order.subtotal}"],
        ]
        
        if order.discount_amount > 0:
            discount_text = f"Discount ({order.discount_type}):"
            if order.discount_type == 'PERCENT':
                discount_text = f"Discount ({order.discount_value}%):"
            totals_data.append([discount_text, f"-₹{order.discount_amount}"])
        
        if order.tax_amount > 0:
            totals_data.append([f"Tax ({order.tax_percent}%):", f"₹{order.tax_amount}"])
        
        if order.tip_amount > 0:
            totals_data.append(['Tip:', f"₹{order.tip_amount}"])
        
        totals_data.append(['Total:', f"₹{order.total}"])
        totals_data.append(['Paid:', f"₹{order.amount_paid}"])
        
        if order.balance_due > 0:
            totals_data.append(['Balance:', f"₹{order.balance_due}"])
        
        totals_table = Table(totals_data, colWidths=[3*inch, 1*inch])
        totals_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -3), (-1, -3), 1, colors.black),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        
        story.append(totals_table)
        story.append(Spacer(1, 12))
        
        # Payment details
        if order.payments.exists():
            payment_data = [['Payment Method', 'Amount']]
            for payment in order.payments.all():
                payment_data.append([payment.get_method_display(), f"₹{payment.amount}"])
            
            payment_table = Table(payment_data, colWidths=[2*inch, 2*inch])
            payment_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            
            story.append(payment_table)
            story.append(Spacer(1, 12))
        
        # QR Code
        qr_data = f"Order: {order.invoice_no or order.id}\nTotal: ₹{order.total}\nDate: {order.created_at.strftime('%Y-%m-%d')}"
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        # Save QR temporarily
        qr_temp_path = os.path.join(settings.MEDIA_ROOT, 'temp_qr.png')
        with open(qr_temp_path, 'wb') as f:
            f.write(qr_buffer.getvalue())
        
        qr_image = Image(qr_temp_path, width=1*inch, height=1*inch)
        
        # Center the QR code
        qr_table = Table([[qr_image]], colWidths=[4.4*inch])
        qr_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        story.append(qr_table)
        story.append(Spacer(1, 12))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER
        )
        
        story.append(Paragraph("Thank you for your business!", footer_style))
        story.append(Paragraph("Please visit again!", footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Clean up temp QR file
        if os.path.exists(qr_temp_path):
            os.remove(qr_temp_path)
        
        # Create receipt record
        with open(filepath, 'rb') as f:
            receipt = PaymentReceipt.objects.create(
                order=order,
                file_name=filename,
                generated_by=user
            )
            receipt.receipt_file.save(filename, ContentFile(f.read()), save=True)
        
        # Clean up temp PDF file
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return receipt

class PaymentService:
    @staticmethod
    def process_refund(payment, refund_amount, user, reason=''):
        """Process a refund for a payment"""
        # This is a placeholder for refund logic
        # In a real system, you'd integrate with payment gateways
        pass