from django.urls import path
from . import views

app_name = 'cms'

urlpatterns = [
    # Public
    path('articles/', views.public_articles, name='public-articles'),
    path('articles/<slug:slug>/', views.public_article_detail, name='public-detail'),

    # Admin
    path('admin/articles/', views.admin_articles, name='admin-articles'),
    path('admin/articles/create/', views.create_article, name='create-article'),
    path('admin/articles/<int:article_id>/', views.update_article, name='update-article'),
    path('stats/', views.cms_stats, name='stats'),
]