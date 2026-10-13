from rest_framework.permissions import BasePermission


class IsAdminOrManager(BasePermission):
    """Allows only users whose role is 'admin' or 'manager'."""

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated
            and (u.is_staff or getattr(u, 'role', None) in ('admin', 'manager'))
        )