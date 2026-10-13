from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction as db_transaction
from decimal import Decimal
import uuid
from django.utils import timezone

from .models import PaymentMethod, Transaction, LockerCredit, Invoice
from .serializers import (
    PaymentMethodSerializer,
    TransactionListSerializer,
    TransactionSerializer,
    LockerCreditSerializer,
    InvoiceSerializer,
)


# ============================================
# PAYMENT METHODS
# ============================================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def payment_methods(request):
    """
    GET  /api/payments/methods/  → list my methods
    POST /api/payments/methods/  → add a method
    """
    if request.method == 'GET':
        qs = PaymentMethod.objects.filter(member=request.user)
        return Response(PaymentMethodSerializer(qs, many=True).data)

    serializer = PaymentMethodSerializer(data=request.data)
    if serializer.is_valid():
        # If it's the first method or marked default, clear others
        make_default = serializer.validated_data.get('is_default', False)
        if not PaymentMethod.objects.filter(member=request.user).exists():
            make_default = True

        if make_default:
            PaymentMethod.objects.filter(member=request.user).update(is_default=False)

        serializer.save(member=request.user, is_default=make_default)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_default_method(request, method_id):
    """
    POST /api/payments/methods/<id>/set-default/
    """
    try:
        method = PaymentMethod.objects.get(id=method_id, member=request.user)
    except PaymentMethod.DoesNotExist:
        return Response({'detail': 'Method not found.'}, status=status.HTTP_404_NOT_FOUND)

    PaymentMethod.objects.filter(member=request.user).update(is_default=False)
    method.is_default = True
    method.save()

    return Response(PaymentMethodSerializer(method).data)


# ============================================
# TRANSACTIONS
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_transactions(request):
    """
    GET /api/payments/transactions/?status=settled
    """
    qs = Transaction.objects.filter(member=request.user)

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.query_params.get('type')
    if type_filter:
        qs = qs.filter(transaction_type=type_filter)

    return Response(TransactionListSerializer(qs[:100], many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail(request, transaction_id):
    """
    GET /api/payments/transactions/<transaction_id>/
    """
    try:
        txn = Transaction.objects.get(transaction_id=transaction_id, member=request.user)
    except Transaction.DoesNotExist:
        return Response({'detail': 'Transaction not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(TransactionSerializer(txn).data)


# ============================================
# LOCKER CREDIT
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_locker_credit(request):
    """
    GET /api/payments/locker-credit/
    """
    credit, _ = LockerCredit.objects.get_or_create(member=request.user)
    return Response(LockerCreditSerializer(credit).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def topup_locker_credit(request):
    """
    POST /api/payments/locker-credit/topup/
    Body: { "amount": 50 }
    """
    try:
        amount = Decimal(str(request.data.get('amount', 0)))
    except Exception:
        return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)

    if amount <= 0:
        return Response({'detail': 'Amount must be positive.'}, status=status.HTTP_400_BAD_REQUEST)

    if amount > 500:
        return Response({'detail': 'Max top-up is $500.'}, status=status.HTTP_400_BAD_REQUEST)

    with db_transaction.atomic():
        credit, _ = LockerCredit.objects.get_or_create(member=request.user)
        credit.balance += amount

        # Cap enforcement
        if credit.balance > credit.max_cap:
            credit.balance = credit.max_cap

        credit.save()

        # Record a transaction
        txn = Transaction.objects.create(
            member=request.user,
            transaction_id=f"#TXN-{uuid.uuid4().hex[:8].upper()}",
            description=f"Locker Credit Top-Up (+${amount})",
            transaction_type='topup',
            amount=amount,
            subtotal=amount,
            status='settled',
            payment_method_label='Default Card',
            settled_at=timezone.now(),
        )

    return Response({
        'credit': LockerCreditSerializer(credit).data,
        'transaction': TransactionListSerializer(txn).data,
    }, status=status.HTTP_201_CREATED)


# ============================================
# INVOICES
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_invoices(request):
    """
    GET /api/payments/invoices/
    """
    qs = Invoice.objects.filter(member=request.user)[:50]
    return Response(InvoiceSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def invoice_detail(request, invoice_number):
    """
    GET /api/payments/invoices/<invoice_number>/
    """
    try:
        invoice = Invoice.objects.get(invoice_number=invoice_number, member=request.user)
    except Invoice.DoesNotExist:
        return Response({'detail': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(InvoiceSerializer(invoice).data)


# ============================================
# PAYMENT SUMMARY (for /payments page)
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_summary(request):
    """
    GET /api/payments/summary/
    Returns KPIs for the payments page dashboard.
    """
    user = request.user
    transactions = Transaction.objects.filter(member=user)

    settled = transactions.filter(status='settled')
    pending = transactions.filter(status='pending')
    refunded = transactions.filter(status='refunded')

    total_spent = sum(t.amount for t in settled if t.amount > 0)
    pending_amount = sum(t.amount for t in pending)
    refunded_amount = sum(abs(t.amount) for t in refunded)

    credit, _ = LockerCredit.objects.get_or_create(member=user)

    return Response({
        'total_transactions': transactions.count(),
        'total_spent': float(total_spent),
        'pending_amount': float(pending_amount),
        'refunded_amount': float(refunded_amount),
        'locker_credit': LockerCreditSerializer(credit).data,
        'pending_invoices': Invoice.objects.filter(member=user, status='pending').count(),
    })