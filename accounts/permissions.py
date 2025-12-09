"""
Custom permissions for role-based access control
"""
from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission check for admin role
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission check for verified users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_verified
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission that allows read-only access to all users,
    but write access only to admins
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'admin'
        )

