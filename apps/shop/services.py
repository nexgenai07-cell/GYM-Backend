"""
Stock reservations. Checkout takes stock off straight away so two members can't buy the last
unit; an order that isn't paid within HOLD_MINUTES gives it back. There's no scheduler on
Vercel, so expiry runs lazily from the shop and admin endpoints. A card payment that lands
after its order expired takes the stock again if it's still there (see payments.gateway).
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Order, Product, PromoCode

HOLD_MINUTES = 30
EXPIRED_NOTE = '[Not paid in time — stock released]'


def release_stock(order):
    """Give an unpaid order's units back (caller holds the order row lock)."""
    for item in order.items.all():
        if item.product_id:
            Product.objects.filter(id=item.product_id).update(
                stock_quantity=F('stock_quantity') + item.quantity, total_sold=F('total_sold') - item.quantity)


def expire_stale_orders():
    """Cancels pending orders older than HOLD_MINUTES that have no payment in flight. Returns the count."""
    cutoff = timezone.now() - timedelta(minutes=HOLD_MINUTES)
    ids = list(Order.objects.filter(status='pending', created_at__lt=cutoff)
               .exclude(payment_intents__status='pending', payment_intents__created_at__gte=cutoff)
               .values_list('id', flat=True)[:200])
    n = 0
    for oid in ids:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(id=oid, status='pending').first()
            if order is None:
                continue
            release_stock(order)
            if order.promo_code:
                PromoCode.objects.filter(code=order.promo_code, used_count__gt=0).update(used_count=F('used_count') - 1)
            order.status = 'cancelled'
            order.notes = f'{order.notes}\n{EXPIRED_NOTE}'.strip()
            order.save(update_fields=['status', 'notes'])
            n += 1
    return n


def retake_stock(order):
    """For a payment that arrived after expiry: reserve the units again if all are in stock."""
    items = list(order.items.all())
    products = {p.id: p for p in Product.objects.select_for_update().filter(id__in=[i.product_id for i in items if i.product_id])}
    if any(i.product_id not in products or products[i.product_id].stock_quantity < i.quantity for i in items):
        return False
    for i in items:
        Product.objects.filter(id=i.product_id).update(
            stock_quantity=F('stock_quantity') - i.quantity, total_sold=F('total_sold') + i.quantity)
    return True
