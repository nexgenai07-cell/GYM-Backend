from django.urls import path

from . import views

app_name = 'site_content'

# Mounted at /api/public/
public_urlpatterns = [
    path('site-content/', views.public_site_content, name='public-site-content'),
    path('contact/', views.public_contact, name='public-contact'),
    path('collections/<slug:name>/', views.public_collection, name='public-collection'),
    path('collections/<slug:name>/<slug:slug>/', views.public_collection_item, name='public-collection-item'),
]

# Mounted at /api/admin/site-content/  (role admin/manager)
urlpatterns = [
    path('pages/', views.admin_pages, name='pages'),
    path('texts/', views.admin_texts, name='texts'),
    path('texts/<str:key>/', views.admin_text_update, name='text-update'),
    path('texts/<str:key>/reset/', views.admin_text_reset, name='text-reset'),
    path('images/', views.admin_images, name='images'),
    path('images/<str:key>/', views.admin_image_update, name='image-update'),
    path('images/<str:key>/reset/', views.admin_image_reset, name='image-reset'),
    path('collections/', views.admin_collections, name='collections'),
    path('collections/<slug:name>/items/', views.admin_collection_items, name='collection-items'),
    path('collections/<slug:name>/items/<int:pk>/', views.admin_collection_item, name='collection-item'),
    path('collections/<slug:name>/items/<int:pk>/image/', views.admin_collection_item_image, name='collection-item-image'),
    path('collections/<slug:name>/items/<int:pk>/image/reset/', views.admin_collection_item_image_reset, name='collection-item-image-reset'),
    path('collections/<slug:name>/reorder/', views.admin_collection_reorder, name='collection-reorder'),
    path('plans/', views.admin_plans, name='plans'),
    path('plans/<int:pk>/', views.admin_plan, name='plan'),
    path('messages/', views.admin_messages, name='messages'),
    path('messages/<int:pk>/', views.admin_message_detail, name='message-detail'),
]
