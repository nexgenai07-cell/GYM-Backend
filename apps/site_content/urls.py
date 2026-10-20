from django.urls import path

from . import views

app_name = 'site_content'

# Mounted at /api/public/
public_urlpatterns = [
    path('site-content/', views.public_site_content, name='public-site-content'),
    path('contact/', views.public_contact, name='public-contact'),
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
    path('messages/', views.admin_messages, name='messages'),
    path('messages/<int:pk>/', views.admin_message_detail, name='message-detail'),
]
