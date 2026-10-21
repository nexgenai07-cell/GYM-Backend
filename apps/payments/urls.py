from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Methods
    path('methods/', views.payment_methods, name='methods'),

    # Transactions
    path('transactions/', views.my_transactions, name='transactions'),
    path('transactions/<str:transaction_id>/', views.transaction_detail, name='transaction-detail'),

    # Locker credit
    path('locker-credit/', views.my_locker_credit, name='locker-credit'),

    # Invoices
    path('invoices/', views.my_invoices, name='invoices'),
    path('invoices/<str:invoice_number>/', views.invoice_detail, name='invoice-detail'),

    # Checkout (Moyasar / locker credit)
    path('checkout/', views.checkout, name='checkout'),
    path('intents/verify/', views.intent_verify, name='intent-verify'),
    path('intents/<int:intent_id>/', views.intent_detail, name='intent-detail'),
    path('intents/<int:intent_id>/attach/', views.intent_attach, name='intent-attach'),

    # Summary
    path('summary/', views.payment_summary, name='payment-summary'),
]