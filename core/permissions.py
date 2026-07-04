from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = []

    def test_func(self):
        return self.request.user.user_type in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['admin']


class ManagerRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['manager']


class EmployeeRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['employee']


class ManagerOrAdminMixin(RoleRequiredMixin):
    allowed_roles = ['admin', 'manager']


class EmployeeBlockedMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Block employees from management/administration views."""

    def test_func(self):
        return self.request.user.user_type != 'employee'

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied('Employees cannot access this area.')
        return super().handle_no_permission()
