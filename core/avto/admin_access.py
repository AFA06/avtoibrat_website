"""Data boundaries for school administrators and teachers."""
from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Assignment, StudyGroup, User


def school_admin_required(view):
    @staff_member_required
    @wraps(view)
    def checked(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return checked


def groups_for(staff):
    groups = StudyGroup.objects.all()
    return groups if staff.is_superuser else groups.filter(teacher=staff)


def students_for(staff):
    students = User.objects.filter(is_staff=False, is_superuser=False)
    return students if staff.is_superuser else students.filter(group__teacher=staff)


def assignments_for(staff):
    assignments = Assignment.objects.all()
    return assignments if staff.is_superuser else assignments.filter(
        Q(audience="group", group__teacher=staff)
        | Q(audience="express", recipient_scope="selected", created_by=staff)
    )
