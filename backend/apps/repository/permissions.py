from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.authentication.models import User


def is_administrator(user):
    return user.is_superuser or user.role == User.Role.ADMIN


class CanPublishResources(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or (
            request.user.role == User.Role.TEACHER or is_administrator(request.user)
        )


class CanManageResource(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return is_administrator(request.user) or (
            request.user.role == User.Role.TEACHER and obj.uploaded_by_id == request.user.id
        )
