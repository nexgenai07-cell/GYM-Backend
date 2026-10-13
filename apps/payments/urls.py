from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Methods
    path('methods/', views.payment_methods, name='methods'),
    path('methods/<int:method_id>/set-default/', views.set_default_method, name='set-default'),

    # Transactions
    path('transactions/', views.my_transactions, name='transactions'),
    path('transactions/<str:transaction_id>/', views.transaction_detail, name='transaction-detail'),

    # Locker credit
    path('locker-credit/', views.my_locker_credit, name='locker-credit'),
    path('locker-credit/topup/', views.topup_locker_credit, name='topup-credit'),

    # Invoices
    path('invoices/', views.my_invoices, name='invoices'),
    path('invoices/<str:invoice_number>/', views.invoice_detail, name='invoice-detail'),

    # Summary
    path('summary/', views.payment_summary, name='payment-summary'),
]