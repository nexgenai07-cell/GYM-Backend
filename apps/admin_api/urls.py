# apps/admin_api/urls.py
from django.urls import path
from . import ops, views

app_name = 'admin_api'

urlpatterns = [
    # Overview
    path('overview/', views.overview, name='overview'),

    # Members
    path('members/', views.members_list, name='members-list'),
    path('members/stats/', views.member_stats, name='member-stats'),
    path('members/bulk-action/', views.bulk_member_action, name='member-bulk-action'),
    path('members/<int:user_id>/', views.member_detail, name='member-detail'),
    path('members/<int:user_id>/update/', views.update_member, name='member-update'),
    path('members/<int:user_id>/action/', views.member_action, name='member-action'),

    # Machines
    path('machines/', views.machines_list, name='machines-list'),
    path('machines/stats/', views.machine_stats, name='machine-stats'),
    path('machines/categories/', views.machine_categories, name='machine-categories'),
    path('machines/<int:exercise_id>/regenerate-qr/', views.regenerate_qr, name='regenerate-qr'),

        # Trainers
    path('trainers/', views.trainers_list_admin, name='trainers-list'),
    path('trainers/stats/', views.trainer_stats_admin, name='trainer-stats'),

        # Staff
    path('staff/', views.staff_list_admin, name='staff-list'),
    path('staff/stats/', views.staff_stats_admin, name='staff-stats'),
    # System settings
    path('settings/', views.system_settings_get, name='settings-get'),
    path('settings/update/', views.system_settings_update, name='settings-update'),
    # Finance
    path('finance/overview/', views.finance_overview, name='finance-overview'),
    path('finance/transactions/', views.transactions_list, name='transactions-list'),
        # Finance extras
    path('finance/revenue-monthly/', views.revenue_monthly, name='revenue-monthly'),
    path('finance/revenue-streams/', views.revenue_streams_view, name='revenue-streams'),
    path('finance/top-members/', views.top_members_view, name='top-members'),
    path('finance/transactions/<int:transaction_id>/', views.transaction_detail, name='transaction-detail'),

    # Dashboard extras
    path('flow-and-revenue/', views.flow_and_revenue, name='flow-and-revenue'),
    path('arena-heatmap/', views.arena_heatmap, name='arena-heatmap'),
    path('audit-feed/', views.audit_feed, name='audit-feed'),
    path('facility-nodes/', views.facility_nodes, name='facility-nodes'),


    # Member purchases back office (ops.py)
    path('facility-pricing/', ops.facility_pricing, name='facility-pricing'),
    path('facility-pricing/<int:item_id>/', ops.facility_pricing_update, name='facility-pricing-update'),
    path('shop/orders/', ops.shop_orders, name='shop-orders'),
    path('shop/orders/<str:order_number>/', ops.shop_order_detail, name='shop-order-detail'),
    path('shop/orders/<str:order_number>/status/', ops.shop_order_status, name='shop-order-status'),
    path('shop/orders/<str:order_number>/refund/', ops.shop_order_refund, name='shop-order-refund'),
    path('payments/review/', ops.payments_review, name='payments-review'),
    path('payments/intents/<int:intent_id>/refund/', ops.payment_refund, name='payment-refund'),
    path('trainer-hours/', ops.trainer_hours, name='trainer-hours'),
    path('trainer-hours/<int:trainer_id>/', ops.trainer_hours_update, name='trainer-hours-update'),
    path('trainer-sessions/', ops.trainer_sessions, name='trainer-sessions'),
    path('trainer-sessions/<int:session_id>/status/', ops.trainer_session_status, name='trainer-session-status'),

    # Analytics
    path('analytics/kpis/', views.analytics_kpis, name='analytics-kpis'),
    path('analytics/growth/', views.analytics_growth, name='analytics-growth'),
    path('analytics/insights/', views.ai_insights, name='ai-insights'),
]