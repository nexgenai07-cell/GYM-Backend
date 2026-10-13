from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Simple health check endpoint."""
    return Response({
        'status': 'healthy',
        'service': 'smart-gym-api',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """API information and available endpoints."""
    return Response({
        'name': 'Smart Gym Digital Ecosystem API',
        'version': '1.0.0',
        'description': 'Backend API for Smart Gym member and admin portals',
        'endpoints': {
            'health': '/api/health/',
            'info': '/api/info/',
            'auth': '/api/auth/ (coming soon)',
            'members': '/api/members/ (coming soon)',
            'admin': '/api/admin/ (coming soon)',
        },
    })