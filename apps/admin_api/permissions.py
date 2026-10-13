from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Only users with role=admin or manager."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ['admin', 'manager']
        )