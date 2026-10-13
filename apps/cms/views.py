# apps/cms/views.py — REPLACE COMPLETELY

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Sum, Q
from django.utils import timezone
import uuid

from .models import Article
from .serializers import ArticleSerializer
from apps.admin_api.permissions import IsAdminUser


# ============================================
# PUBLIC (member-facing blog)
# ============================================
@api_view(['GET'])
@permission_classes([AllowAny])
def public_articles(request):
    """
    GET /api/cms/articles/
    """
    qs = Article.objects.filter(status='published').order_by('-published_at')

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)

    if request.query_params.get('featured') == 'true':
        qs = qs.filter(is_featured=True)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(excerpt__icontains=search)
        )

    return Response(ArticleSerializer(qs[:50], many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_article_detail(request, slug):
    """
    GET /api/cms/articles/<slug>/
    """
    try:
        article = Article.objects.get(slug=slug, status='published')
    except Article.DoesNotExist:
        return Response({'detail': 'Article not found.'}, status=404)

    article.views_count = (article.views_count or 0) + 1
    article.save(update_fields=['views_count'])

    return Response(ArticleSerializer(article).data)


# ============================================
# ADMIN
# ============================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_articles(request):
    """
    GET /api/cms/admin/articles/
    """
    qs = Article.objects.select_related('author').all()

    status = request.query_params.get('status')
    if status and status != 'all':
        qs = qs.filter(status=status)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(category__icontains=search)
        )

    return Response(ArticleSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def cms_stats(request):
    """
    GET /api/cms/stats/
    """
    total = Article.objects.count()
    published = Article.objects.filter(status='published').count()
    drafts = Article.objects.filter(status='draft').count()
    total_views = Article.objects.aggregate(v=Sum('views_count'))['v'] or 0

    return Response({
        'total_articles': total,
        'published': published,
        'drafts': drafts,
        'total_views': total_views,
        'newsletter_subs': 4820,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def create_article(request):
    """
    POST /api/cms/admin/articles/
    """
    article_id = f"ART-{uuid.uuid4().hex[:4].upper()}"

    data = request.data.copy()
    data['article_id'] = article_id

    serializer = ArticleSerializer(data=data)
    if serializer.is_valid():
        serializer.save(author=request.user)
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_article(request, article_id):
    """
    PATCH/DELETE /api/cms/admin/articles/<id>/
    """
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if request.method == 'DELETE':
        article.delete()
        return Response(status=204)

    serializer = ArticleSerializer(article, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)