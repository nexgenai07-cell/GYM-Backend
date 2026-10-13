from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal
import uuid
from django.db.models import Q

from .models import (
    ProductCategory, Product,
    Cart, CartItem,
    Order, OrderItem,
    PromoCode,
)
from .serializers import (
    ProductCategorySerializer,
    ProductListSerializer, ProductDetailSerializer,
    CartSerializer, CartItemSerializer,
    OrderListSerializer, OrderDetailSerializer,
    PromoCodeSerializer,
)


# ============================================
# CATEGORIES (public)
# ============================================
@api_view(['GET'])
@permission_classes([AllowAny])
def categories_list(request):
    """
    GET /api/shop/categories/
    """
    qs = ProductCategory.objects.filter(is_active=True)
    return Response(ProductCategorySerializer(qs, many=True).data)


# ============================================
# PRODUCTS (public)
# ============================================
# apps/shop/views.py — replace the top imports and products_list
@api_view(['GET'])
@permission_classes([AllowAny])
def products_list(request):
    """
    GET /api/shop/products/
    Query params: ?category=protein&search=&featured=true&in_stock=true
    """
    qs = Product.objects.filter(is_active=True).select_related('category')

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category__key=category)

    if request.query_params.get('featured') == 'true':
        qs = qs.filter(is_featured=True)

    if request.query_params.get('in_stock') == 'true':
        qs = qs.filter(stock_quantity__gt=0)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    return Response(ProductListSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail(request, product_id):
    """
    GET /api/shop/products/<id>/
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)
    return Response(ProductDetailSerializer(product).data)


# ============================================
# CART
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart(request):
    """
    GET /api/shop/cart/
    """
    cart, _ = Cart.objects.get_or_create(member=request.user)
    return Response(CartSerializer(cart).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    """
    POST /api/shop/cart/add/
    Body: { "product_id": 5, "quantity": 1 }
    """
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity', 1))

    if quantity <= 0:
        return Response({'detail': 'Quantity must be positive.'}, status=status.HTTP_400_BAD_REQUEST)

    product = get_object_or_404(Product, id=product_id, is_active=True)

    if product.is_out_of_stock:
        return Response({'detail': 'Product is out of stock.'}, status=status.HTTP_400_BAD_REQUEST)

    if quantity > product.stock_quantity:
        return Response(
            {'detail': f'Only {product.stock_quantity} units available.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cart, _ = Cart.objects.get_or_create(member=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, product=product,
        defaults={'quantity': quantity},
    )
    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_cart_item(request, item_id):
    """
    PATCH /api/shop/cart/items/<id>/
    Body: { "quantity": 3 }
    """
    try:
        item = CartItem.objects.get(id=item_id, cart__member=request.user)
    except CartItem.DoesNotExist:
        return Response({'detail': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        quantity = int(request.data.get('quantity', 1))
    except (ValueError, TypeError):
        return Response({'detail': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

    if quantity <= 0:
        item.delete()
        return Response(CartSerializer(item.cart).data)

    if quantity > item.product.stock_quantity:
        return Response(
            {'detail': f'Only {item.product.stock_quantity} units available.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    item.quantity = quantity
    item.save()

    return Response(CartSerializer(item.cart).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_cart_item(request, item_id):
    """
    DELETE /api/shop/cart/items/<id>/
    """
    try:
        item = CartItem.objects.get(id=item_id, cart__member=request.user)
    except CartItem.DoesNotExist:
        return Response({'detail': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)

    cart = item.cart
    item.delete()
    return Response(CartSerializer(cart).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_cart(request):
    """
    POST /api/shop/cart/clear/
    """
    cart, _ = Cart.objects.get_or_create(member=request.user)
    cart.items.all().delete()
    return Response(CartSerializer(cart).data)


# ============================================
# PROMO CODES
# ============================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_promo(request):
    """
    POST /api/shop/cart/apply-promo/
    Body: { "code": "PRO15" }
    """
    code = request.data.get('code', '').strip().upper()
    if not code:
        return Response({'detail': 'Code is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        promo = PromoCode.objects.get(code=code)
    except PromoCode.DoesNotExist:
        return Response({'detail': 'Invalid promo code.'}, status=status.HTTP_404_NOT_FOUND)

    if not promo.is_valid:
        return Response({'detail': 'Promo code is no longer valid.'}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'code': promo.code,
        'discount_percent': float(promo.discount_percent),
        'description': promo.description,
    })


# ============================================
# CHECKOUT → ORDER
# ============================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout(request):
    """
    POST /api/shop/checkout/
    Body: { "delivery_method": "locker", "promo_code": "PRO15", "notes": "..." }
    Converts cart → order, decrements stock.
    """
    cart, _ = Cart.objects.get_or_create(member=request.user)

    if cart.items.count() == 0:
        return Response({'detail': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

    delivery_method = request.data.get('delivery_method', 'locker')
    promo_code_str = request.data.get('promo_code', '').strip().upper()
    notes = request.data.get('notes', '')

    with db_transaction.atomic():
        # Compute totals
        subtotal = Decimal('0.00')
        for item in cart.items.all():
            subtotal += item.product.price * item.quantity

        # Promo
        discount = Decimal('0.00')
        promo = None
        if promo_code_str:
            promo = PromoCode.objects.filter(code=promo_code_str).first()
            if promo and promo.is_valid:
                discount = (subtotal * promo.discount_percent) / Decimal('100')

        taxable = subtotal - discount
        tax = (taxable * Decimal('0.05')).quantize(Decimal('0.01'))  # 5% VAT
        total = taxable + tax

        # Create order
        order_number = f"#ORD-{uuid.uuid4().hex[:6].upper()}"
        order = Order.objects.create(
            order_number=order_number,
            member=request.user,
            status='pending',
            delivery_method=delivery_method,
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            total=total,
            promo_code=promo_code_str if promo else '',
            notes=notes,
            locker_number=f"LKR-{uuid.uuid4().hex[:4].upper()}" if delivery_method == 'locker' else '',
        )

        # Create order items + decrement stock
        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                product_sku=item.product.sku,
                unit_price=item.product.price,
                quantity=item.quantity,
                line_total=item.product.price * item.quantity,
            )

            # Decrement stock
            item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
            item.product.total_sold += item.quantity
            item.product.save(update_fields=['stock_quantity', 'total_sold'])

        # Promo use count
        if promo:
            promo.used_count += 1
            promo.save(update_fields=['used_count'])

        # Clear cart
        cart.items.all().delete()

    return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)


# ============================================
# ORDERS
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_orders(request):
    """
    GET /api/shop/orders/
    Query params: ?status=dispatched
    """
    qs = Order.objects.filter(member=request.user)

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    return Response(OrderListSerializer(qs[:50], many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_number):
    """
    GET /api/shop/orders/<order_number>/
    """
    try:
        order = Order.objects.get(order_number=order_number, member=request.user)
    except Order.DoesNotExist:
        return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(OrderDetailSerializer(order).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order(request, order_number):
    """
    POST /api/shop/orders/<order_number>/cancel/
    """
    try:
        order = Order.objects.get(order_number=order_number, member=request.user)
    except Order.DoesNotExist:
        return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

    if order.status not in ['pending', 'paid', 'preparing']:
        return Response(
            {'detail': 'Order can no longer be cancelled.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with db_transaction.atomic():
        # Restore stock
        for item in order.items.all():
            if item.product:
                item.product.stock_quantity += item.quantity
                item.product.save(update_fields=['stock_quantity'])

        order.status = 'cancelled'
        order.save()

    return Response(OrderDetailSerializer(order).data)