from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    # Catalog
    path('categories/', views.categories_list, name='categories'),
    path('products/', views.products_list, name='products'),
    path('products/<int:product_id>/', views.product_detail, name='product-detail'),

    # Cart
    path('cart/', views.get_cart, name='cart'),
    path('cart/add/', views.add_to_cart, name='cart-add'),
    path('cart/items/<int:item_id>/', views.update_cart_item, name='cart-update'),
    path('cart/items/<int:item_id>/remove/', views.remove_cart_item, name='cart-remove'),
    path('cart/clear/', views.clear_cart, name='cart-clear'),
    path('cart/apply-promo/', views.apply_promo, name='apply-promo'),

    # Checkout
    path('checkout/', views.checkout, name='checkout'),

    # Orders
    path('orders/', views.my_orders, name='orders'),
    path('orders/<str:order_number>/', views.order_detail, name='order-detail'),
    path('orders/<str:order_number>/cancel/', views.cancel_order, name='order-cancel'),
]