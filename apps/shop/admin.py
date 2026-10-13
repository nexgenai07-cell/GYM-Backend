from django.contrib import admin
from .models import (
    ProductCategory, Product,
    Cart, CartItem,
    Order, OrderItem,
    PromoCode,
)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'key', 'display_order', 'is_active']
    list_filter = ['is_active']
    prepopulated_fields = {'key': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'price', 'stock_quantity', 'is_active', 'is_featured']
    list_filter = ['category', 'is_active', 'is_featured']
    search_fields = ['name', 'sku']
    prepopulated_fields = {'sku': ('name',)}


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['member', 'item_count', 'subtotal', 'updated_at']
    search_fields = ['member__email']
    raw_id_fields = ['member']
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product_name', 'product_sku', 'unit_price', 'line_total']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'member', 'status', 'total', 'created_at']
    list_filter = ['status', 'delivery_method', 'created_at']
    search_fields = ['order_number', 'member__email']
    raw_id_fields = ['member']
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_percent', 'used_count', 'max_uses', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code']