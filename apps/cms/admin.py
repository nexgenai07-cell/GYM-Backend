from django.contrib import admin
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['article_id', 'title', 'category', 'status', 'is_featured', 'views_count', 'created_at']
    list_filter = ['status', 'category', 'is_featured']
    search_fields = ['title', 'article_id', 'category']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ['author']
    date_hierarchy = 'created_at'