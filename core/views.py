from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.http import FileResponse, Http404
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.views import View
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.core.cache import cache
from django.forms import formset_factory
import json
import mimetypes
import time
from urllib.parse import quote

from .models import (
    CustomUser, Company, PackageTemplate, PackageAuthorization, PackageInstance,
    AuthorizedForm, LibraryDocument, DropdownList, DropdownOption, Project,
    TeamMember, EmployeeRecord, FormRecord, FormReview, FormDefinition, FormTableLayout,
    SubPackage, Notification, notify_user, FORM_TYPE_CHOICES, USER_ROLE_CHOICES,
)
from .forms import (
    EmailLoginForm, UserRegistrationForm, AdminRegistrationForm, AdminUserEditForm,
    AdminSelfProfileForm, ManagerRegistrationForm, ManagerUserEditForm, UserProfileEditForm, AdminSetPasswordForm,
    SelfPasswordChangeForm,
    CompanyForm, PackageAuthorizationForm, LibraryDocumentForm,
    CompanyCreateForm, CompanyEditForm, company_edit_initial,
    DropdownListForm, DropdownOptionForm, ProjectForm, TeamMemberForm, TeamMemberEditForm,
    EmployeeRecordForm, FormRecordForm, CVApprovalForm, ViewPackageSearchForm,
    ProjectAccessForm, FormDetailsForm, FormTableLayoutForm,
)
from .access import (
    can_access_project, can_access_form, can_create_form_record,
    can_access_library_document, get_authorized_library_documents,
    get_employee_projects, get_team_member, can_view_report, get_manager_manageable_users,
    company_for_project,
)
from .permissions import AdminRequiredMixin, ManagerRequiredMixin, EmployeeBlockedMixin, ManagerOrAdminMixin
from .context_processors import invalidate_notification_cache
from .form_table_utils import (
    build_table_block, block_from_post, table_block_keys, stored_cells_for_layout,
)
from .package_seed import get_active_package_template


def admin_users_success_redirect(action, username=''):
    """Redirect to admin list with a popup action flag."""
    url = reverse('core:users')
    query = f'success={action}'
    if username:
        query += f'&user={quote(username)}'
    return redirect(f'{url}?{query}')


def company_list_success_redirect(action, company_name='', projects=''):
    """Redirect to company list with a popup action flag."""
    url = reverse('core:company-list')
    query = f'success={action}'
    if company_name:
        query += f'&company={quote(company_name)}'
    if projects:
        query += f'&projects={quote(str(projects))}'
    return redirect(f'{url}?{query}')


def form_details_list_success_redirect(action, form_code=''):
    """Redirect to form details list with a popup action flag."""
    url = reverse('core:form-details-list')
    query = f'success={action}'
    if form_code:
        query += f'&form={quote(form_code)}'
    return redirect(f'{url}?{query}')


def form_table_list_success_redirect(action, form_code=''):
    """Redirect to form table list with a popup action flag."""
    url = reverse('core:form-table-list')
    query = f'success={action}'
    if form_code:
        query += f'&form={quote(form_code)}'
    return redirect(f'{url}?{query}')


def form_table_view_list_success_redirect(action, form_code=''):
    """Redirect to view tables list with a popup action flag."""
    url = reverse('core:form-table-view-list')
    query = f'success={action}'
    if form_code:
        query += f'&form={quote(form_code)}'
    return redirect(f'{url}?{query}')


def manager_users_success_redirect(action, username=''):
    """Redirect to user list with a manager user-action popup flag."""
    url = reverse('core:users')
    query = f'success={action}'
    if username:
        query += f'&user={quote(username)}'
    return redirect(f'{url}?{query}')


def user_profile_success_redirect(profile_id, action='updated', username=''):
    """Redirect to user profile with a popup action flag."""
    url = reverse('core:user', args=[profile_id])
    query = f'success={action}'
    if username:
        query += f'&user={quote(username)}'
    return redirect(f'{url}?{query}')


def project_detail_success_redirect(pk, action, project_number='', access_password=''):
    """Redirect to project detail with a popup action flag."""
    url = reverse('core:project-detail', args=[pk])
    query = f'success={action}'
    if project_number:
        query += f'&project={quote(project_number)}'
    if access_password:
        query += f'&access_password={quote(access_password)}'
    return redirect(f'{url}?{query}')


def project_list_redirect(**params):
    """Redirect to project list with popup query flags."""
    url = reverse('core:project-list')
    query = '&'.join(f'{key}={quote(str(value))}' for key, value in params.items())
    return redirect(f'{url}?{query}')


# --- Authentication ---
class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return render(request, 'core/login.html', {'form': EmailLoginForm()})

    def post(self, request):
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            user = authenticate(request, username=form.cleaned_data['email'],
                                password=form.cleaned_data['password'])
            if user:
                login(request, user)
                display_name = user.first_name or user.username or user.email.split('@')[0]
                messages.success(request, f'Welcome back, {display_name}!')
                return redirect('core:dashboard')
            messages.error(request, 'Invalid email or password.')
        return render(request, 'core/login.html', {'form': form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        messages.info(request, 'You have been logged out.')
        return redirect('core:login')


class IndexView(View):
    def get(self, request):
        return redirect('core:dashboard' if request.user.is_authenticated else 'core:login')


class DashboardView(LoginRequiredMixin, View):
    _CACHE_TTL = 60

    def get(self, request):
        user = request.user
        ctx = {'user': user}
        if user.user_type == 'admin':
            cache_key = f'dashboard_stats_admin_{user.pk}'
            cached = cache.get(cache_key)
            if cached is not None:
                ctx.update(cached)
                return render(request, 'core/dashboard.html', ctx)

            user_stats = CustomUser.objects.aggregate(
                admin_count=Count('id', filter=Q(user_type='admin')),
                manager_count=Count('id', filter=Q(user_type='manager')),
                employee_count=Count('id', filter=Q(user_type='employee')),
            )
            ctx.update(user_stats)
            ctx.update({
                'company_count': Company.objects.count(),
                'authorization_count': PackageAuthorization.objects.count(),
                'form_details_count': _admin_form_definitions().count(),
                'library_count': LibraryDocument.objects.count(),
            })
            cache.set(cache_key, {k: v for k, v in ctx.items() if k != 'user'}, self._CACHE_TTL)
        elif user.user_type == 'manager':
            manager_cache_key = f'dashboard_stats_manager_{user.pk}'
            cached = cache.get(manager_cache_key)
            if cached is not None:
                ctx.update(cached)
                return render(request, 'core/dashboard.html', ctx)

            project_count = Project.objects.filter(manager=user).count()
            projects = list(Project.objects.filter(manager=user).order_by('-pk')[:5])
            company = _manager_company(user)
            auth = PackageAuthorization.objects.filter(manager=user).order_by('-created_at').first()
            manager_stats = TeamMember.objects.filter(
                project__manager=user, is_active=True,
            ).aggregate(team_member_count=Count('id'))
            manager_ctx = {
                'projects': projects,
                'project_count': project_count,
                'total_projects_allocated': company.project_limit if company else 0,
                'remaining_projects': max(0, company.project_limit - project_count) if company else 0,
                'allocated_forms_count': (
                    AuthorizedForm.objects.filter(authorization=auth, is_active=True).count()
                    if auth else 0
                ),
                'team_member_count': manager_stats['team_member_count'],
                'pending_reviews': FormRecord.objects.filter(
                    project__manager=user, status='submitted'
                ).count(),
            }
            ctx.update(manager_ctx)
            cache.set(manager_cache_key, manager_ctx, self._CACHE_TTL)
        else:
            employee_cache_key = f'dashboard_stats_employee_{user.pk}'
            cached = cache.get(employee_cache_key)
            if cached is not None:
                ctx.update(cached)
                return render(request, 'core/dashboard.html', ctx)

            assignments = get_employee_projects(user)
            team_projects = [a.project for a in assignments]
            form_stats = FormRecord.objects.filter(created_by_user=user).aggregate(
                form_count=Count('id'),
                pending_forms=Count('id', filter=Q(status__in=['draft', 'returned'])),
            )
            employee_ctx = {
                'projects': team_projects,
                'assignments': assignments,
                'form_count': form_stats['form_count'],
                'pending_forms': form_stats['pending_forms'],
                'library_count': get_authorized_library_documents(user).count(),
            }
            ctx.update(employee_ctx)
            cache.set(employee_cache_key, employee_ctx, self._CACHE_TTL)
        return render(request, 'core/dashboard.html', ctx)


# --- User Management ---
class RegisterView(ManagerOrAdminMixin, View):
    def _form_for_user(self, user, data=None):
        if user.user_type == 'admin':
            form_class = AdminRegistrationForm
            creating_admin = True
        else:
            form_class = ManagerRegistrationForm
            creating_admin = False
        if data is None:
            return form_class(user=user), creating_admin
        return form_class(data, user=user), creating_admin

    def get(self, request):
        form, creating_admin = self._form_for_user(request.user)
        return render(request, 'core/reg_form.html', {
            'form': form,
            'creating_admin': creating_admin,
        })

    def post(self, request):
        form, creating_admin = self._form_for_user(request.user, request.POST)
        if form.is_valid():
            new_user = form.save()
            if creating_admin:
                return admin_users_success_redirect('created', new_user.username)
            display_name = new_user.get_full_name() or new_user.username
            return manager_users_success_redirect('created', display_name)
        return render(request, 'core/reg_form.html', {
            'form': form,
            'creating_admin': creating_admin,
        })


class UsersView(ManagerOrAdminMixin, View):
    def get(self, request):
        user = request.user
        search = request.GET.get('search', '').strip()
        user_role_filter = request.GET.get('user_role', '')

        if user.user_type == 'admin':
            users = CustomUser.objects.filter(user_type='admin')
            if search:
                users = users.filter(
                    Q(username__icontains=search)
                    | Q(email__icontains=search)
                    | Q(first_name__icontains=search)
                    | Q(last_name__icontains=search)
                )
        elif user.user_type == 'manager':
            users = get_manager_manageable_users(user).select_related('under_supervision')
            if user_role_filter:
                users = users.filter(user_role=user_role_filter)
            if search:
                users = users.filter(
                    Q(username__icontains=search)
                    | Q(email__icontains=search)
                    | Q(first_name__icontains=search)
                    | Q(last_name__icontains=search)
                )
        else:
            return redirect('core:dashboard')

        users = users.order_by('-date_joined')
        paginator = Paginator(users, 20)
        page_obj = paginator.get_page(request.GET.get('page'))

        return render(request, 'core/users.html', {
            'users': page_obj,
            'total_users': paginator.count,
            'logged_user': user,
            'user_role_filter': user_role_filter,
            'user_role_choices': USER_ROLE_CHOICES,
            'search_query': search,
            'admin_users_only': user.user_type == 'admin',
            'can_manage_all_listed': user.user_type in ('admin', 'manager'),
            'success_action': request.GET.get('success', ''),
            'success_user': request.GET.get('user', ''),
        })


class ManagerTeamListView(ManagerRequiredMixin, View):
    """Manager: view authorized team members across all projects."""
    def get(self, request):
        members = TeamMember.objects.filter(
            project__manager=request.user,
            is_active=True,
        ).select_related('project', 'user').order_by('project__project_number', 'name')
        return render(request, 'core/team_member_list.html', {
            'team_members': members,
            'total_members': members.count(),
        })


class UserProfileView(LoginRequiredMixin, View):
    def get(self, request, profile_id):
        profile = get_object_or_404(CustomUser, id=profile_id)
        if not request.user.can_manage_user(profile) and request.user != profile:
            messages.error(request, 'Access denied.')
            return redirect('core:dashboard')
        project_authorizations = (
            profile.team_assignments.filter(is_active=True)
            .select_related('project')
            .order_by('project__project_number')
        )
        return render(request, 'core/user.html', {
            'user_view': profile,
            'project_authorizations': project_authorizations,
            'success_action': request.GET.get('success', ''),
            'success_user': request.GET.get('user', ''),
        })


class ProfileView(LoginRequiredMixin, View):
    def _profile_form(self, user, data=None):
        if user.user_type == 'admin':
            form_class = AdminSelfProfileForm
        else:
            form_class = UserProfileEditForm
        if data is None:
            return form_class(instance=user)
        return form_class(data, instance=user)

    def get(self, request):
        user = request.user
        return render(request, 'core/profile.html', {
            'form': self._profile_form(user),
            'is_admin_profile': user.user_type == 'admin',
        })

    def post(self, request):
        user = request.user
        form = self._profile_form(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('core:profile')
        return render(request, 'core/profile.html', {
            'form': form,
            'is_admin_profile': user.user_type == 'admin',
        })


class ProfilePasswordResetView(LoginRequiredMixin, View):
    """Allow employees and managers to reset their own password."""
    def get(self, request):
        if request.user.user_type == 'admin':
            return redirect('core:admin-set-password', user_id=request.user.id)
        return render(request, 'core/profile_reset_password.html', {
            'form': SelfPasswordChangeForm(request.user),
        })

    def post(self, request):
        if request.user.user_type == 'admin':
            return redirect('core:admin-set-password', user_id=request.user.id)
        form = SelfPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data['new_password1'])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Your password has been updated successfully.')
            return redirect('core:profile')
        return render(request, 'core/profile_reset_password.html', {'form': form})


class EditUserProfileView(LoginRequiredMixin, View):
    def _edit_form(self, editor, target, data=None):
        if editor.user_type == 'admin':
            form_class = AdminUserEditForm
        elif editor.user_type == 'manager' and target.user_type in ('manager', 'employee'):
            form_class = ManagerUserEditForm
        else:
            form_class = UserProfileEditForm
        if data is None:
            return form_class(instance=target)
        return form_class(data, instance=target)

    def get(self, request, user_id):
        target = get_object_or_404(CustomUser, id=user_id)
        if not request.user.can_manage_user(target):
            messages.error(request, 'Access denied.')
            return redirect('core:dashboard')
        return render(request, 'core/edit_user_profile.html', {
            'form': self._edit_form(request.user, target),
            'target_user': target,
            'editing_admin': request.user.user_type == 'admin' and target.user_type == 'admin',
        })

    def post(self, request, user_id):
        target = get_object_or_404(CustomUser, id=user_id)
        if not request.user.can_manage_user(target):
            return redirect('core:dashboard')
        form = self._edit_form(request.user, target, request.POST)
        if form.is_valid():
            updated = form.save(commit=False)
            if request.user.user_type == 'manager' and updated.user_type == 'employee':
                updated.under_supervision = request.user
            updated.save()
            if updated.user_type == 'employee':
                display_name = updated.get_full_name() or updated.username
                TeamMember.objects.filter(user=updated, is_active=True).update(name=display_name)
            if request.user.user_type == 'admin' and target.user_type == 'admin':
                return admin_users_success_redirect('updated', updated.username)
            display_name = updated.get_full_name() or updated.username
            return user_profile_success_redirect(target.id, 'updated', display_name)
        return render(request, 'core/edit_user_profile.html', {
            'form': form,
            'target_user': target,
            'editing_admin': request.user.user_type == 'admin' and target.user_type == 'admin',
        })


class UserDeleteView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if request.user.user_type == 'manager':
            messages.error(request, 'Managers cannot delete users. Use Activate/Deactivate instead.')
            return redirect('core:users')
        target = get_object_or_404(CustomUser, id=pk)
        if not request.user.can_manage_user(target) or target == request.user:
            messages.error(request, 'Cannot delete this user.')
            return redirect('core:users')
        return render(request, 'core/delete_user.html', {'target_user': target})

    def post(self, request, pk):
        if request.user.user_type == 'manager':
            messages.error(request, 'Managers cannot delete users. Use Activate/Deactivate instead.')
            return redirect('core:users')
        target = get_object_or_404(CustomUser, id=pk)
        if request.user.can_manage_user(target) and target != request.user:
            username = target.get_full_name() or target.username
            is_admin = target.user_type == 'admin'
            target.delete()
            if is_admin:
                return admin_users_success_redirect('deleted', username)
            return manager_users_success_redirect('deleted', username)
        return redirect('core:users')


class UserToggleActiveView(LoginRequiredMixin, View):
    """Managers activate/deactivate their users instead of deleting them."""

    def post(self, request, pk):
        if request.user.user_type != 'manager':
            messages.error(request, 'Only managers can use this action here.')
            return redirect('core:users')
        target = get_object_or_404(CustomUser, id=pk)
        if target == request.user:
            messages.error(request, 'You cannot change your own account status.')
            return redirect('core:users')
        if not request.user.can_manage_user(target):
            messages.error(request, 'Access denied.')
            return redirect('core:users')
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        username = target.get_full_name() or target.username
        action = 'activated' if target.is_active else 'deactivated'
        return manager_users_success_redirect(action, username)


class AdminSetPasswordView(ManagerOrAdminMixin, View):
    def get(self, request, user_id):
        target = get_object_or_404(CustomUser, id=user_id)
        if not request.user.can_manage_user(target):
            messages.error(request, 'Access denied.')
            return redirect('core:users')
        return render(request, 'core/admin_set_password.html', {'form': AdminSetPasswordForm(), 'target_user': target})

    def post(self, request, user_id):
        target = get_object_or_404(CustomUser, id=user_id)
        if not request.user.can_manage_user(target):
            return redirect('core:users')
        form = AdminSetPasswordForm(request.POST)
        if form.is_valid():
            target.set_password(form.cleaned_data['new_password1'])
            target.save()
            if target.user_type == 'admin':
                return admin_users_success_redirect('password', target.username)
            messages.success(request, 'Password updated.')
            return redirect('core:user', profile_id=target.id)
        return render(request, 'core/admin_set_password.html', {'form': form, 'target_user': target})


# --- Admin: Companies ---
def _company_search_q(search):
    """Search across company, manager, and package authorization fields."""
    q = (
        Q(name__icontains=search)
        | Q(location__icontains=search)
        | Q(abbreviation__icontains=search)
        | Q(version__icontains=search)
        | Q(designated_person__icontains=search)
        | Q(client_email__icontains=search)
        | Q(authorized_manager__username__icontains=search)
        | Q(authorized_manager__email__icontains=search)
        | Q(authorized_manager__first_name__icontains=search)
        | Q(authorized_manager__last_name__icontains=search)
        | Q(authorized_manager__package_authorizations__vvb_name__icontains=search)
        | Q(authorized_manager__package_authorizations__abbreviation__icontains=search)
    )
    if search.isdigit():
        num = int(search)
        q |= Q(project_limit=num)
        q |= Q(authorized_manager__package_authorizations__package_count=num)
        q |= Q(authorized_manager__package_authorizations__year=num)
        if len(search) == 4:
            q |= Q(issue_date__year=num)
    return q


class CompanyListView(AdminRequiredMixin, ListView):
    model = Company
    template_name = 'core/company_list.html'
    context_object_name = 'companies'

    def get_queryset(self):
        qs = Company.objects.select_related('authorized_manager').order_by('-created_at')
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(_company_search_q(search)).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        search = self.request.GET.get('search', '').strip()
        ctx['search_query'] = search
        ctx['total_companies'] = Company.objects.count()
        ctx['filtered_count'] = self.get_queryset().count()

        manager_ids = [
            c.authorized_manager_id for c in ctx['companies'] if c.authorized_manager_id
        ]
        auths = {}
        for auth in PackageAuthorization.objects.filter(manager_id__in=manager_ids).order_by('-created_at'):
            auths.setdefault(auth.manager_id, auth)

        for company in ctx['companies']:
            company.package_auth = auths.get(company.authorized_manager_id)

        ctx['success_action'] = self.request.GET.get('success', '')
        ctx['success_company'] = self.request.GET.get('company', '')
        ctx['success_projects'] = self.request.GET.get('projects', '')
        return ctx


def _admin_form_definitions(queryset=None):
    """Forms created by admin via Form Details (excludes removed seed data)."""
    qs = queryset if queryset is not None else FormDefinition.objects.all()
    return qs.filter(created_by__isnull=False)


def _form_definitions_by_type(form_definitions):
    """Group form definitions under their form-type headings."""
    by_type = {key: [] for key, _ in FORM_TYPE_CHOICES}
    for form_def in form_definitions:
        by_type.setdefault(form_def.form_type, []).append(form_def)
    return [
        {'key': key, 'label': label, 'forms': by_type[key]}
        for key, label in FORM_TYPE_CHOICES
        if by_type.get(key)
    ]


def _company_package_context(package_template):
    if not package_template:
        package_template = get_active_package_template()
    if not package_template:
        return {
            'form_definitions': [],
            'form_definition_groups': [],
            'package_template': None,
        }
    form_definitions = _admin_form_definitions(
        FormDefinition.objects.filter(
            sub_package__package_template=package_template,
        )
    ).order_by('order', 'code')
    return {
        'package_template': package_template,
        'form_definitions': form_definitions,
        'form_definition_groups': _form_definitions_by_type(form_definitions),
    }


def _company_authorization(company):
    if not company.authorized_manager_id:
        return None
    return PackageAuthorization.objects.filter(
        manager_id=company.authorized_manager_id,
    ).order_by('-created_at').first()


def _activated_form_ids(authorization):
    if not authorization:
        return set()
    return set(
        AuthorizedForm.objects.filter(
            authorization=authorization, is_active=True,
        ).values_list('form_definition_id', flat=True)
    )


def _apply_activated_forms(authorization, activated_ids):
    """Set authorized forms active only for checked form definition IDs."""
    AuthorizedForm.objects.filter(authorization=authorization).update(is_active=False)
    if activated_ids:
        AuthorizedForm.objects.filter(
            authorization=authorization,
            form_definition_id__in=activated_ids,
        ).update(is_active=True)


class CompanyCreateView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'core/company_form.html', {
            'form': CompanyCreateForm(),
            'title': 'Create Company',
            'is_create': True,
        })

    @transaction.atomic
    def post(self, request):
        form = CompanyCreateForm(request.POST)
        package_template = get_active_package_template()

        if form.is_valid():
            if not package_template:
                form.add_error(None, 'No active package template found. Create a package template first.')
            else:
                first_name, last_name = form.split_manager_name()
                company = Company.objects.create(
                    name=form.cleaned_data['name'],
                    abbreviation=form.cleaned_data['abbreviation'],
                    issue_date=form.cleaned_data.get('issue_date'),
                    version=form.cleaned_data.get('version', ''),
                    designated_person=form.cleaned_data.get('designated_person', ''),
                    client_contact=form.cleaned_data.get('client_contact', ''),
                    client_email=form.cleaned_data['client_email'],
                    project_limit=form.cleaned_data['project_limit'],
                    created_by=request.user,
                )
                mgr = CustomUser.objects.create_user(
                    username=form.cleaned_data['manager_username'],
                    email=form.cleaned_data['client_email'],
                    password=form.cleaned_data['access_password'],
                    first_name=first_name,
                    last_name=last_name,
                    user_type='manager',
                    company=company,
                    created_by=request.user,
                )
                company.authorized_manager = mgr
                company.save()

                issue_date = form.cleaned_data.get('issue_date')
                start_date = form.cleaned_data['start_date']
                project_limit = form.cleaned_data['project_limit']
                auth = PackageAuthorization.objects.create(
                    package_template=package_template,
                    manager=mgr,
                    vvb_name=company.name,
                    abbreviation=company.abbreviation,
                    year=(issue_date or start_date).year,
                    start_date=start_date,
                    end_date=form.cleaned_data['end_date'],
                    package_count=project_limit,
                    access_password=form.cleaned_data['access_password'],
                    created_by=request.user,
                )
                auth.generate_package_instances()

                return company_list_success_redirect(
                    'created', company.name, company.project_limit,
                )

        return render(request, 'core/company_form.html', {
            'form': form,
            'title': 'Create Company',
            'is_create': True,
        })


class CompanyUpdateView(AdminRequiredMixin, View):
    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        auth = _company_authorization(company)
        package_template = (
            auth.package_template if auth
            else get_active_package_template()
        )
        form = CompanyEditForm(
            initial=company_edit_initial(company, auth),
            company=company,
        )
        return render(request, 'core/company_form.html', {
            'form': form,
            'title': 'Edit Company',
            'company': company,
            'is_edit': True,
            'activated_form_ids': _activated_form_ids(auth),
            **_company_package_context(package_template),
        })

    @transaction.atomic
    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        auth = _company_authorization(company)
        package_template = (
            auth.package_template if auth
            else get_active_package_template()
        )
        form = CompanyEditForm(request.POST, company=company)
        pkg_ctx = _company_package_context(package_template)
        pkg_ctx['activated_form_ids'] = set(
            int(x) for x in request.POST.getlist('activated_forms') if x.isdigit()
        )

        if form.is_valid():
            first_name, last_name = form.split_manager_name()
            company.name = form.cleaned_data['name']
            company.abbreviation = form.cleaned_data['abbreviation']
            company.issue_date = form.cleaned_data.get('issue_date')
            company.version = form.cleaned_data.get('version', '')
            company.designated_person = form.cleaned_data.get('designated_person', '')
            company.client_contact = form.cleaned_data.get('client_contact', '')
            company.client_email = form.cleaned_data['client_email']
            company.project_limit = form.cleaned_data['project_limit']
            company.save()

            mgr = company.authorized_manager
            new_password = form.cleaned_data.get('access_password')
            if not mgr:
                mgr = CustomUser.objects.create_user(
                    username=form.cleaned_data['manager_username'],
                    email=form.cleaned_data['client_email'],
                    password=new_password or 'changeme123',
                    first_name=first_name,
                    last_name=last_name,
                    user_type='manager',
                    company=company,
                    created_by=request.user,
                )
                company.authorized_manager = mgr
                company.save()
            else:
                mgr.username = form.cleaned_data['manager_username']
                mgr.email = form.cleaned_data['client_email']
                mgr.first_name = first_name
                mgr.last_name = last_name
                if new_password:
                    mgr.set_password(new_password)
                mgr.company = company
                mgr.save()

            issue_date = form.cleaned_data.get('issue_date')
            start_date = form.cleaned_data['start_date']
            project_limit = form.cleaned_data['project_limit']
            if auth:
                auth.vvb_name = company.name
                auth.abbreviation = company.abbreviation
                auth.year = (issue_date or start_date).year
                auth.start_date = start_date
                auth.end_date = form.cleaned_data['end_date']
                auth.package_count = project_limit
                if new_password:
                    auth.access_password = new_password
                auth.save()
                auth.generate_package_instances()
            elif package_template:
                auth = PackageAuthorization.objects.create(
                    package_template=package_template,
                    manager=mgr,
                    vvb_name=company.name,
                    abbreviation=company.abbreviation,
                    year=(issue_date or start_date).year,
                    start_date=start_date,
                    end_date=form.cleaned_data['end_date'],
                    package_count=project_limit,
                    access_password=new_password or '',
                    created_by=request.user,
                )
                auth.generate_package_instances()

            if auth:
                _apply_activated_forms(
                    auth,
                    request.POST.getlist('activated_forms'),
                )

            return company_list_success_redirect('updated', company.name)

        return render(request, 'core/company_form.html', {
            'form': form,
            'title': 'Edit Company',
            'company': company,
            'is_edit': True,
            **pkg_ctx,
        })


class CompanyDetailView(AdminRequiredMixin, View):
    def _context(self, company, auth):
        mgr = company.authorized_manager
        pm_name = ''
        if mgr:
            pm_name = (mgr.get_full_name() or '').strip() or mgr.username

        active_count = inactive_count = 0
        activated_form_ids = set()
        pkg_ctx = {'form_definitions': [], 'form_definition_groups': []}
        if auth:
            for af in AuthorizedForm.objects.filter(
                authorization=auth,
            ).select_related('form_definition').order_by('form_definition__code'):
                if af.is_active:
                    active_count += 1
                else:
                    inactive_count += 1
            activated_form_ids = _activated_form_ids(auth)
            pkg_ctx = _company_package_context(auth.package_template)

        return {
            'company': company,
            'authorization': auth,
            'manager_name': pm_name,
            'active_form_count': active_count,
            'inactive_form_count': inactive_count,
            'activated_form_ids': activated_form_ids,
            **pkg_ctx,
        }

    def get(self, request, pk):
        company = get_object_or_404(
            Company.objects.select_related('authorized_manager'), pk=pk,
        )
        auth = _company_authorization(company)
        return render(request, 'core/company_detail.html', self._context(company, auth))

    @transaction.atomic
    def post(self, request, pk):
        company = get_object_or_404(
            Company.objects.select_related('authorized_manager'), pk=pk,
        )
        auth = _company_authorization(company)
        if auth:
            _apply_activated_forms(auth, request.POST.getlist('activated_forms'))
            messages.success(request, 'Form allocation saved for this company.')
        else:
            messages.error(request, 'No package authorization linked to this company.')
        return redirect('core:company-detail', pk=pk)


class CompanyDeleteView(AdminRequiredMixin, DeleteView):
    model = Company
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('core:company-list')
    context_object_name = 'object'


# --- Admin: Form Details (FormDefinition) ---
def _default_sub_package_for_new_form():
    template = get_active_package_template()
    if not template:
        return None
    return (
        template.sub_packages.filter(code='P1-C').first()
        or template.sub_packages.order_by('order').first()
    )


class FormDetailsListView(AdminRequiredMixin, ListView):
    model = FormDefinition
    template_name = 'core/form_details_list.html'
    context_object_name = 'forms'

    def get_queryset(self):
        return _admin_form_definitions(
            FormDefinition.objects.select_related(
                'sub_package', 'sub_package__package_template', 'created_by',
            )
        ).order_by('code')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_definition_groups'] = _form_definitions_by_type(ctx['forms'])
        ctx['success_action'] = self.request.GET.get('success', '')
        ctx['success_form'] = self.request.GET.get('form', '')
        return ctx


class FormDetailsCreateView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'core/form_details_form.html', {
            'form': FormDetailsForm(),
            'title': 'Create Form Details',
        })

    def post(self, request):
        form = FormDetailsForm(request.POST)
        if form.is_valid():
            sub_package = _default_sub_package_for_new_form()
            if not sub_package:
                form.add_error(
                    None,
                    'Could not assign a sub-package for this form. Please contact support.',
                )
            else:
                form_def = form.save(commit=False)
                form_def.sub_package = sub_package
                form_def.order = sub_package.forms.count()
                form_def.created_by = request.user
                form_def.save()
                for auth in PackageAuthorization.objects.filter(
                    package_template=sub_package.package_template,
                ):
                    AuthorizedForm.objects.get_or_create(
                        authorization=auth,
                        form_definition=form_def,
                        defaults={'is_active': False},
                    )
                return form_details_list_success_redirect('created', form_def.code)
        return render(request, 'core/form_details_form.html', {
            'form': form,
            'title': 'Create Form Details',
        })


class FormDetailsUpdateView(AdminRequiredMixin, View):
    def get(self, request, pk):
        form_def = get_object_or_404(FormDefinition, pk=pk, created_by__isnull=False)
        return render(request, 'core/form_details_form.html', {
            'form': FormDetailsForm(instance=form_def),
            'title': 'Edit Form Details',
            'form_def': form_def,
        })

    def post(self, request, pk):
        form_def = get_object_or_404(FormDefinition, pk=pk, created_by__isnull=False)
        form = FormDetailsForm(request.POST, instance=form_def)
        if form.is_valid():
            form.save()
            return form_details_list_success_redirect('updated', form_def.code)
        return render(request, 'core/form_details_form.html', {
            'form': form,
            'title': 'Edit Form Details',
            'form_def': form_def,
        })


class FormDetailsDeleteView(AdminRequiredMixin, DeleteView):
    model = FormDefinition
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('core:form-details-list')

    def get_queryset(self):
        return _admin_form_definitions()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Delete Form Details'
        return ctx

    def form_valid(self, form):
        form_code = self.object.code
        self.object.delete()
        return form_details_list_success_redirect('deleted', form_code)


class FormDetailsDetailView(AdminRequiredMixin, DetailView):
    model = FormDefinition
    template_name = 'core/form_details_detail.html'
    context_object_name = 'form_def'

    def get_queryset(self):
        return _admin_form_definitions()


# --- Admin: Create Tables In Form ---
class FormTableInFormListView(AdminRequiredMixin, ListView):
    model = FormDefinition
    template_name = 'core/form_table_list.html'
    context_object_name = 'forms'

    def get_queryset(self):
        return _admin_form_definitions(
            FormDefinition.objects.prefetch_related('table_layouts').select_related('created_by')
        ).order_by('code')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_definition_groups'] = _form_definitions_by_type(ctx['forms'])
        ctx['success_action'] = self.request.GET.get('success', '')
        ctx['success_form'] = self.request.GET.get('form', '')
        return ctx


class FormTableLayoutEditView(AdminRequiredMixin, View):
    """Define one or more table layouts for a form."""

    def _form_def(self, pk):
        return get_object_or_404(_admin_form_definitions(), pk=pk)

    def _table_blocks(self, form_def, post=None):
        if post is not None:
            keys = table_block_keys(post)
            if not keys:
                return [build_table_block(key='new0')]
            return [
                block_from_post(post, key, table_number=index)
                for index, key in enumerate(keys, start=1)
            ]
        layouts = list(form_def.table_layouts.all())
        if layouts:
            return [build_table_block(layout=layout) for layout in layouts]
        return [build_table_block(key='new0')]

    def get(self, request, pk):
        form_def = self._form_def(pk)
        table_blocks = self._table_blocks(form_def)
        has_tables = any(block.get('layout_id') for block in table_blocks)
        return render(request, 'core/form_table_edit.html', {
            'form_def': form_def,
            'table_blocks': table_blocks,
            'empty_block': build_table_block(key='new0'),
            'has_tables': has_tables,
        })

    def post(self, request, pk):
        form_def = self._form_def(pk)
        blocks = self._table_blocks(form_def, request.POST)
        valid_blocks = []
        has_error = False
        for block in blocks:
            if not block:
                has_error = True
                continue
            if not block.get('columns'):
                has_error = True
                block['error'] = 'Add at least one column heading.'
            valid_blocks.append(block)
        if has_error:
            return render(request, 'core/form_table_edit.html', {
                'form_def': form_def,
                'table_blocks': valid_blocks or [build_table_block(key='new0')],
                'empty_block': build_table_block(key='new0'),
                'has_tables': any(block.get('layout_id') for block in valid_blocks),
                'form_error': 'Fix the highlighted table blocks before saving.',
            })

        removed_ids = {
            int(value) for value in request.POST.get('removed_table_ids', '').split(',')
            if value.strip().isdigit()
        }
        kept_ids = set()
        # Free unique table_number slots before rewriting order.
        with transaction.atomic():
            existing_ids = [
                block['layout_id'] for block in valid_blocks if block.get('layout_id')
            ]
            if existing_ids:
                for offset, layout_id in enumerate(existing_ids, start=1):
                    FormTableLayout.objects.filter(
                        pk=layout_id, form_definition=form_def,
                    ).update(table_number=10000 + offset)

            for block in valid_blocks:
                defaults = {
                    'table_number': block['table_number'],
                    'table_name': block['table_name'],
                    'table_heading': block['table_heading'],
                    'notes': block['notes'],
                    'table_note': block['table_note'],
                    'row_count': block['row_count'],
                    'column_headers': block['columns'],
                    'cell_dropdowns': block['cell_dropdowns'],
                    'created_by': request.user,
                }
                if block['layout_id']:
                    layout, _ = FormTableLayout.objects.update_or_create(
                        pk=block['layout_id'],
                        form_definition=form_def,
                        defaults=defaults,
                    )
                else:
                    layout = FormTableLayout.objects.create(
                        form_definition=form_def,
                        **defaults,
                    )
                kept_ids.add(layout.pk)

            form_def.table_layouts.filter(pk__in=removed_ids - kept_ids).delete()
        if request.GET.get('return') == 'view' or request.POST.get('return') == 'view':
            return form_table_view_list_success_redirect('saved', form_def.code)
        return form_table_list_success_redirect('saved', form_def.code)


# --- Admin: View Tables In Form ---
class FormTableViewInFormListView(AdminRequiredMixin, ListView):
    model = FormDefinition
    template_name = 'core/form_table_view_list.html'
    context_object_name = 'forms'

    def get_queryset(self):
        return _admin_form_definitions(
            FormDefinition.objects.prefetch_related('table_layouts').select_related('created_by')
        ).order_by('code')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_definition_groups'] = _form_definitions_by_type(ctx['forms'])
        ctx['success_action'] = self.request.GET.get('success', '')
        ctx['success_form'] = self.request.GET.get('form', '')
        return ctx


class FormTableLayoutDetailView(AdminRequiredMixin, View):
    """Read-only view of all table layouts for a form."""
    def get(self, request, pk):
        form_def = get_object_or_404(_admin_form_definitions(), pk=pk)
        layouts = list(form_def.table_layouts.all())
        if not layouts:
            messages.error(request, 'No table has been created for this form yet.')
            return redirect('core:form-table-view-list')
        table_blocks = []
        for layout in layouts:
            preview_row_cells = [
                {
                    'col': col_idx,
                    'label': column['label'],
                    'dropdown': layout.dropdown_for_cell(0, col_idx),
                }
                for col_idx, column in layout.active_columns()
            ]
            table_blocks.append({
                'layout': layout,
                'preview_row_cells': preview_row_cells,
                'column_dropdowns': layout.normalized_column_dropdowns(),
            })
        return render(request, 'core/form_table_detail.html', {
            'form_def': form_def,
            'table_blocks': table_blocks,
        })


class FormTableLayoutDeleteView(AdminRequiredMixin, View):
    """Delete all table layouts for a form, not the form definition."""
    def post(self, request, pk):
        form_def = get_object_or_404(_admin_form_definitions(), pk=pk)
        if not form_def.table_layouts.exists():
            messages.error(request, 'No table exists for this form.')
            return redirect('core:form-table-view-list')
        form_code = form_def.code
        form_def.table_layouts.all().delete()
        return form_table_view_list_success_redirect('deleted', form_code)


# --- Admin: Package Authorization ---
class PackageAuthorizationListView(AdminRequiredMixin, ListView):
    model = PackageAuthorization
    template_name = 'core/package_authorization_list.html'
    context_object_name = 'authorizations'


class PackageAuthorizationCreateView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'core/package_authorization_form.html', {
            'form': PackageAuthorizationForm(), 'title': 'Authorize Packages'
        })

    def post(self, request):
        form = PackageAuthorizationForm(request.POST)
        if form.is_valid():
            auth = form.save(commit=False)
            auth.created_by = request.user
            auth.save()
            auth.generate_package_instances()
            messages.success(request, f'Authorized {auth.package_count} packages for {auth.vvb_name}.')
            return redirect('core:package-authorization-detail', pk=auth.pk)
        return render(request, 'core/package_authorization_form.html', {'form': form, 'title': 'Authorize Packages'})


class PackageAuthorizationUpdateView(AdminRequiredMixin, View):
    def get(self, request, pk):
        auth = get_object_or_404(PackageAuthorization, pk=pk)
        return render(request, 'core/package_authorization_form.html', {
            'form': PackageAuthorizationForm(instance=auth), 'title': 'Update Package Authorization', 'authorization': auth
        })

    def post(self, request, pk):
        auth = get_object_or_404(PackageAuthorization, pk=pk)
        form = PackageAuthorizationForm(request.POST, instance=auth)
        if form.is_valid():
            auth = form.save()
            auth.generate_package_instances()
            messages.success(request, 'Package authorization updated.')
            return redirect('core:package-authorization-detail', pk=auth.pk)
        return render(request, 'core/package_authorization_form.html', {'form': form, 'title': 'Update Package Authorization', 'authorization': auth})


class PackageAuthorizationDetailView(AdminRequiredMixin, DetailView):
    model = PackageAuthorization
    template_name = 'core/package_authorization_detail.html'
    context_object_name = 'authorization'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['authorized_forms'] = AuthorizedForm.objects.filter(
            authorization=self.object
        ).select_related('form_definition')
        ctx['instances'] = self.object.instances.all()
        return ctx


class PackageAuthorizationDeleteView(AdminRequiredMixin, DeleteView):
    model = PackageAuthorization
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('core:package-authorization-list')


class ToggleAuthorizedFormView(AdminRequiredMixin, View):
    def post(self, request, pk):
        af = get_object_or_404(AuthorizedForm, pk=pk)
        af.is_active = not af.is_active
        af.save()
        messages.success(request, f'{af.form_definition.code} {"activated" if af.is_active else "deactivated"}.')
        return redirect('core:package-authorization-detail', pk=af.authorization.pk)


# --- Admin: Library Documents ---
class LibraryDocumentListView(LoginRequiredMixin, ListView):
    model = LibraryDocument
    template_name = 'core/library_list.html'
    context_object_name = 'documents'

    def get_queryset(self):
        return get_authorized_library_documents(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['error_action'] = self.request.GET.get('error', '')
        return context


class LibraryDocumentCreateView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'core/library_form.html', {
            'form': LibraryDocumentForm(),
            'title': 'Upload Information',
        })

    def post(self, request):
        form = LibraryDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.save()
            _sync_library_document_access(doc)
            messages.success(request, 'Document uploaded to the Documents Library.')
            return redirect('core:library-list')
        return render(request, 'core/library_form.html', {'form': form, 'title': 'Upload Information'})


class LibraryDocumentDeleteView(AdminRequiredMixin, DeleteView):
    model = LibraryDocument
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('core:library-list')


def _library_redirect_with_error(request, error_code):
    """Redirect back to the library list, preserving the Documents tab, with an error popup flag."""
    url = reverse('core:library-list')
    params = []
    if 'view=documents' in request.META.get('HTTP_REFERER', ''):
        params.append('view=documents')
    params.append(f'error={error_code}')
    return redirect(f'{url}?{"&".join(params)}')


def _serve_library_document(request, pk, as_attachment):
    doc = get_object_or_404(LibraryDocument, pk=pk)
    if not can_access_library_document(request.user, doc):
        return _library_redirect_with_error(request, 'unauthorized')
    if as_attachment and request.user.user_type != 'admin':
        return _library_redirect_with_error(request, 'download_forbidden')
    if not doc.file:
        return _library_redirect_with_error(request, 'file_missing')
    filename = doc.file.name.split('/')[-1]
    content_type, _ = mimetypes.guess_type(filename)
    try:
        file_handle = doc.file.open('rb')
    except (FileNotFoundError, ValueError, OSError):
        return _library_redirect_with_error(request, 'file_missing')
    return FileResponse(
        file_handle,
        as_attachment=as_attachment,
        filename=filename if as_attachment else None,
        content_type=content_type or 'application/octet-stream',
    )


class LibraryViewView(LoginRequiredMixin, View):
    def get(self, request, pk):
        return _serve_library_document(request, pk, as_attachment=False)


class LibraryDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        return _serve_library_document(request, pk, as_attachment=True)


# --- Admin: Dropdown Lists ---
class DropdownListView(AdminRequiredMixin, ListView):
    model = DropdownList
    template_name = 'core/dropdown_list.html'
    context_object_name = 'dropdown_lists'


class DropdownListEditView(AdminRequiredMixin, View):
    def get(self, request, pk):
        ddl = get_object_or_404(DropdownList, pk=pk)
        options = ddl.options.all()
        return render(request, 'core/dropdown_edit.html', {
            'dropdown': ddl,
            'options': options,
            'option_form': DropdownOptionForm(),
            'list_form': DropdownListForm(instance=ddl),
        })

    def post(self, request, pk):
        ddl = get_object_or_404(DropdownList, pk=pk)
        action = request.POST.get('action')
        if action == 'update_list':
            form = DropdownListForm(request.POST, instance=ddl)
            if form.is_valid():
                form.save()
                messages.success(request, 'Drop-down list updated.')
        elif action == 'add_option':
            form = DropdownOptionForm(request.POST)
            if form.is_valid():
                opt = form.save(commit=False)
                opt.dropdown_list = ddl
                opt.save()
                messages.success(request, 'Option added.')
        elif action == 'update_option':
            opt = get_object_or_404(DropdownOption, pk=request.POST.get('option_id'), dropdown_list=ddl)
            opt.value = request.POST.get('value', opt.value)
            opt.order = int(request.POST.get('order', opt.order) or 0)
            opt.is_active = request.POST.get('is_active') == 'on'
            opt.save()
            messages.success(request, 'Option updated.')
        elif action == 'delete_option':
            DropdownOption.objects.filter(pk=request.POST.get('option_id'), dropdown_list=ddl).delete()
            messages.success(request, 'Option removed.')
        return redirect('core:dropdown-edit', pk=pk)


class DropdownListDeleteView(AdminRequiredMixin, DeleteView):
    model = DropdownList
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('core:dropdown-list')
    context_object_name = 'object'


class DropdownListCreateView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'core/dropdown_form.html', {'form': DropdownListForm(), 'title': 'Create Drop-Down List'})

    def post(self, request):
        form = DropdownListForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Drop-down list created.')
            return redirect('core:dropdown-list')
        return render(request, 'core/dropdown_form.html', {'form': form, 'title': 'Create Drop-Down List'})


# --- Admin: View Package (backup support) ---
class ViewPackageSearchView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'core/view_package_search.html', {'form': ViewPackageSearchForm()})

    def post(self, request):
        form = ViewPackageSearchForm(request.POST)
        if form.is_valid():
            auths = PackageAuthorization.objects.filter(
                vvb_name__icontains=form.cleaned_data['vvb_name']
            ).select_related('package_template', 'manager').prefetch_related(
                'instances', 'authorized_library__library_document',
                'authorized_forms__form_definition',
            )
            return render(request, 'core/view_package_results.html', {
                'authorizations': auths,
                'form': form,
                'read_only': True,
            })
        return render(request, 'core/view_package_search.html', {'form': form})


# --- Manager: Employee Records ---
class EmployeeRecordListView(ManagerRequiredMixin, ListView):
    model = EmployeeRecord
    template_name = 'core/employee_record_list.html'
    context_object_name = 'employees'

    def get_queryset(self):
        return EmployeeRecord.objects.filter(manager=self.request.user)


class EmployeeRecordCreateView(ManagerRequiredMixin, View):
    def get(self, request):
        return render(request, 'core/employee_record_form.html', {'form': EmployeeRecordForm(), 'title': 'Create Employee Record'})

    def post(self, request):
        form = EmployeeRecordForm(request.POST, request.FILES)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.manager = request.user
            rec.save()
            messages.success(request, 'Employee record created.')
            return redirect('core:employee-record-list')
        return render(request, 'core/employee_record_form.html', {'form': form, 'title': 'Create Employee Record'})


class EmployeeRecordUpdateView(ManagerRequiredMixin, View):
    def get(self, request, pk):
        rec = get_object_or_404(EmployeeRecord, pk=pk, manager=request.user)
        return render(request, 'core/employee_record_form.html', {'form': EmployeeRecordForm(instance=rec), 'title': 'Edit Employee Record', 'record': rec})

    def post(self, request, pk):
        rec = get_object_or_404(EmployeeRecord, pk=pk, manager=request.user)
        form = EmployeeRecordForm(request.POST, request.FILES, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, 'Employee record updated.')
            return redirect('core:employee-record-list')
        return render(request, 'core/employee_record_form.html', {'form': form, 'title': 'Edit Employee Record', 'record': rec})


class EmployeeRecordDeleteView(ManagerRequiredMixin, DeleteView):
    model = EmployeeRecord
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('core:employee-record-list')

    def get_queryset(self):
        return EmployeeRecord.objects.filter(manager=self.request.user)


class CVApprovalView(ManagerRequiredMixin, View):
    def get(self, request):
        employees = EmployeeRecord.objects.filter(manager=request.user)
        return render(request, 'core/cv_review.html', {'employees': employees})


class CVApprovalUpdateView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        rec = get_object_or_404(EmployeeRecord, pk=pk, manager=request.user)
        form = CVApprovalForm(request.POST, instance=rec)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.cv_approved_by = request.user
            rec.cv_approved_at = timezone.now()
            rec.save()
            messages.success(request, f'CV status for {rec.name} updated to {rec.get_cv_approval_status_display()}.')
        return redirect('core:cv-review')


# --- Manager: Projects ---
class ProjectListView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        if user.user_type == 'manager':
            projects = Project.objects.filter(manager=user).select_related(
                'package_instance', 'package_instance__authorization'
            )
            assignments = None
        elif user.user_type == 'employee':
            assignments = get_employee_projects(user)
            projects = [a.project for a in assignments]
        elif user.user_type == 'admin':
            projects = Project.objects.all().select_related(
                'package_instance', 'package_instance__authorization', 'manager'
            )
            assignments = None
        else:
            projects = Project.objects.none()
            assignments = None
        return render(request, 'core/project_list.html', {
            'projects': projects,
            'assignments': assignments,
            'success_action': request.GET.get('success', ''),
            'error_action': request.GET.get('error', ''),
            'project_limit': request.GET.get('limit', ''),
        })


def _manager_company(user):
    try:
        return user.managed_company
    except Company.DoesNotExist:
        return user.company


def _manager_at_project_limit(user):
    company = _manager_company(user)
    if not company:
        return False, None
    return company.manager_project_count() >= company.project_limit, company


def _next_package_instance_for_manager(manager):
    """Pick the next unused package instance for a manager's authorization."""
    auth = PackageAuthorization.objects.filter(manager=manager).order_by('-created_at').first()
    if not auth:
        return None
    used_ids = set(
        Project.objects.filter(manager=manager).values_list('package_instance_id', flat=True)
    )
    inst = auth.instances.exclude(id__in=used_ids).order_by('package_number').first()
    if inst:
        return inst
    return auth.instances.order_by('package_number').first()


class ProjectCreateView(ManagerRequiredMixin, View):
    def get(self, request):
        at_limit, company = _manager_at_project_limit(request.user)
        if at_limit:
            return project_list_redirect(
                error='project_limit',
                limit=company.project_limit,
            )
        form = ProjectForm()
        return render(request, 'core/project_form.html', {'form': form, 'title': 'Create Project'})

    def post(self, request):
        at_limit, company = _manager_at_project_limit(request.user)
        if at_limit:
            return project_list_redirect(
                error='project_limit',
                limit=company.project_limit,
            )
        form = ProjectForm(request.POST)
        if form.is_valid():
            package_instance = _next_package_instance_for_manager(request.user)
            if not package_instance:
                form.add_error(
                    None,
                    'No package instance is available. Contact your administrator to authorize packages.',
                )
                return render(request, 'core/project_form.html', {'form': form, 'title': 'Create Project'})
            project = form.save(commit=False)
            project.manager = request.user
            project.package_instance = package_instance
            project.save()
            return project_detail_success_redirect(
                project.pk,
                'created',
                project.project_number,
                project.access_password,
            )
        return render(request, 'core/project_form.html', {'form': form, 'title': 'Create Project'})


def _build_project_form_groups(project, user=None, form_types=None):
    """Authorized admin-created forms for a project, grouped by sub-package."""
    auth = project.package_instance.authorization
    template = auth.package_template
    active_form_ids = set(
        AuthorizedForm.objects.filter(
            authorization=auth, is_active=True,
        ).values_list('form_definition_id', flat=True)
    )
    records = FormRecord.objects.filter(project=project).select_related('form_definition')
    record_by_form = {r.form_definition_id: r for r in records}
    allowed_types = set(form_types) if form_types else None
    restrict_to_project_type = (
        user is not None
        and user.is_authenticated
        and user.user_type == 'employee'
    )
    sub_packages = []
    for sub in template.sub_packages.prefetch_related('forms'):
        form_rows = []
        for f in sub.forms.filter(created_by__isnull=False):
            if f.id not in active_form_ids:
                continue
            if allowed_types is not None and f.form_type not in allowed_types:
                continue
            if restrict_to_project_type and f.form_type != 'project':
                continue
            form_rows.append({
                'form_def': f,
                'record': record_by_form.get(f.id),
            })
        if form_rows:
            sub_packages.append({'sub_package': sub, 'form_rows': form_rows})
    return sub_packages


def _build_manager_forms_by_type(projects, form_types=None):
    """Unique allocated forms across all projects, grouped by form type only."""
    allowed_types = set(form_types) if form_types else None
    by_type = {key: {} for key, _ in FORM_TYPE_CHOICES}
    for project in projects.order_by('project_number'):
        for group in _build_project_form_groups(project):
            for row in group['form_rows']:
                form_def = row['form_def']
                if allowed_types is not None and form_def.form_type not in allowed_types:
                    continue
                bucket = by_type.setdefault(form_def.form_type, {})
                existing = bucket.get(form_def.id)
                if existing is None:
                    bucket[form_def.id] = {
                        'form_def': form_def,
                        'project': project,
                        'record': row['record'],
                    }
                elif row['record'] and not existing['record']:
                    existing['record'] = row['record']
                    existing['project'] = project
    type_order = (
        [(key, label) for key, label in FORM_TYPE_CHOICES if key in allowed_types]
        if allowed_types is not None
        else list(FORM_TYPE_CHOICES)
    )
    return [
        {
            'key': key,
            'label': label,
            'form_rows': sorted(
                by_type[key].values(),
                key=lambda item: item['form_def'].code,
            ),
        }
        for key, label in type_order
        if by_type.get(key)
    ]


def _manager_view_forms_response(request, form_types=None, page_title='View All Forms', page_description=''):
    projects = Project.objects.filter(
        manager=request.user,
    ).select_related(
        'package_instance',
        'package_instance__authorization',
        'package_instance__authorization__package_template',
    ).order_by('project_number')
    if not page_description:
        page_description = (
            'All forms allocated by the administrator, grouped by form type. '
            'Team users only see and can work with Project type forms on project pages.'
        )
    return render(request, 'core/manager_view_forms.html', {
        'form_type_groups': _build_manager_forms_by_type(projects, form_types=form_types),
        'has_projects': projects.exists(),
        'page_title': page_title,
        'page_description': page_description,
    })


class ManagerViewFormsView(ManagerRequiredMixin, View):
    """Manager: view all allocated forms grouped by form type."""
    def get(self, request):
        return _manager_view_forms_response(request)


class ManagerViewMasterRecordView(ManagerRequiredMixin, View):
    """Manager: view allocated Master Record forms."""
    def get(self, request):
        return _manager_view_forms_response(
            request,
            form_types=['master_record'],
            page_title='View Master Record',
            page_description='Master Record forms allocated by the administrator.',
        )


class ManagerViewProposalFormsView(ManagerRequiredMixin, View):
    """Manager: view allocated Proposal forms."""
    def get(self, request):
        return _manager_view_forms_response(
            request,
            form_types=['proposal'],
            page_title='View Proposal Forms',
            page_description='Proposal forms allocated by the administrator.',
        )


class ProjectDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        if not can_access_project(request.user, project, request.session):
            messages.error(request, 'Access denied.')
            return redirect('core:dashboard')
        auth = project.package_instance.authorization
        sub_packages = _build_project_form_groups(
            project, request.user, form_types=['project'],
        )
        records = FormRecord.objects.filter(project=project).select_related('form_definition')
        report_records = [
            r for r in records if can_view_report(request.user, r)
        ]
        team_member = get_team_member(request.user, project)
        return render(request, 'core/project_detail.html', {
            'project': project,
            'sub_packages': sub_packages,
            'team_members': project.team_members.filter(is_active=True),
            'vvb_password': auth.access_password,
            'team_member': team_member,
            'can_authorize_library': get_authorized_library_documents(request.user).exists(),
            'report_records': report_records,
            'success_action': request.GET.get('success', ''),
            'success_project': request.GET.get('project', ''),
            'success_access_password': request.GET.get('access_password', ''),
        })


class ProjectUpdateView(ManagerOrAdminMixin, View):
    def _get_project(self, request, pk):
        if request.user.user_type == 'admin':
            return get_object_or_404(Project, pk=pk)
        return get_object_or_404(Project, pk=pk, manager=request.user)

    def get(self, request, pk):
        project = self._get_project(request, pk)
        return render(request, 'core/project_form.html', {'form': ProjectForm(instance=project), 'title': 'Edit Project', 'project': project})

    def post(self, request, pk):
        project = self._get_project(request, pk)
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            return project_detail_success_redirect(
                project.pk,
                'updated',
                project.project_number,
            )
        return render(request, 'core/project_form.html', {'form': form, 'title': 'Edit Project', 'project': project})


class ProjectDeleteView(AdminRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        return render(request, 'core/confirm_delete.html', {
            'object': project,
            'title': 'Delete Project',
            'cancel_url': reverse('core:project-detail', args=[project.pk]),
        })

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        project_number = project.project_number
        project.delete()
        messages.success(request, f'Project {project_number} deleted.')
        return redirect('core:project-list')


# --- Manager: Team Authorization ---
class TeamMemberCreateView(ManagerRequiredMixin, View):
    def _formset_class(self):
        return formset_factory(TeamMemberForm, extra=1)

    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id, manager=request.user)
        formset = self._formset_class()(form_kwargs={'manager': request.user})
        return render(request, 'core/team_member_form.html', {'formset': formset, 'project': project})

    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id, manager=request.user)
        formset = self._formset_class()(request.POST, form_kwargs={'manager': request.user})
        if formset.is_valid():
            access_url = request.build_absolute_uri(reverse('core:project-access', args=[project.pk]))
            authorized_names = []
            for form in formset:
                if not form.cleaned_data:
                    continue
                selected_user = form.cleaned_data.get('user')
                if not selected_user:
                    continue

                selected_user.user_role = form.cleaned_data['user_role']
                if form.cleaned_data.get('designation'):
                    selected_user.designation = form.cleaned_data['designation']
                if form.cleaned_data.get('position_title'):
                    selected_user.position_title = form.cleaned_data['position_title']
                selected_user.save()

                member_name = selected_user.get_full_name() or selected_user.username
                TeamMember.objects.update_or_create(
                    project=project,
                    email=selected_user.email,
                    defaults={
                        'name': member_name,
                        'role': 'team_member',
                        'user_role': form.cleaned_data['user_role'],
                        'designation': form.cleaned_data.get('designation', ''),
                        'position_title': form.cleaned_data.get('position_title', ''),
                        'user': selected_user,
                        'is_active': True,
                    },
                )
                notify_user(
                    selected_user,
                    f'You are authorized for project {project.project_number}. '
                    f'Access: {access_url}',
                    sender=request.user,
                    link=reverse('core:project-access', args=[project.pk]),
                )
                authorized_names.append(member_name)

            if authorized_names:
                messages.success(
                    request,
                    f'{", ".join(authorized_names)} authorized. Notification sent.'
                )
                return redirect('core:project-detail', pk=project.pk)
            messages.error(request, 'Select at least one user to authorize.')
        return render(request, 'core/team_member_form.html', {'formset': formset, 'project': project})


class TeamMemberEditView(ManagerRequiredMixin, View):
    """Edit an authorized member's user role, designation and position for a project."""
    def get(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk, project__manager=request.user)
        form = TeamMemberEditForm(instance=member)
        return render(request, 'core/team_member_edit_form.html', {'form': form, 'member': member})

    def post(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk, project__manager=request.user)
        form = TeamMemberEditForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            if member.user:
                member.user.user_role = member.user_role
                member.user.designation = member.designation
                member.user.position_title = member.position_title
                member.user.save()
            messages.success(request, f'{member.name} updated for project {member.project.project_number}.')
            return redirect('core:project-detail', pk=member.project_id)
        return render(request, 'core/team_member_edit_form.html', {'form': form, 'member': member})


class TeamMemberDeleteView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk, project__manager=request.user)
        project_id = member.project_id
        member.is_active = False
        member.save()
        messages.success(request, f'{member.name} was removed from this project. Their user account is still in the system.')
        return redirect('core:project-detail', pk=project_id)


_FORM_RECORD_SELECT = (
    'project',
    'project__manager',
    'project__manager__managed_company',
    'project__manager__company',
    'form_definition',
    'project__package_instance',
    'project__package_instance__authorization',
)


def _get_form_record(pk):
    return get_object_or_404(
        FormRecord.objects.select_related(*_FORM_RECORD_SELECT),
        pk=pk,
    )


# --- Form Records & Workflow ---
class FormRecordCreateView(LoginRequiredMixin, View):
    def get(self, request, project_id, form_id):
        project = get_object_or_404(
            Project.objects.select_related(
                'manager', 'manager__managed_company', 'manager__company',
                'package_instance', 'package_instance__authorization',
            ),
            pk=project_id,
        )
        form_def = get_object_or_404(FormDefinition, pk=form_id)
        if not can_create_form_record(request.user, project, form_def):
            messages.error(request, 'You are not authorized to create this form record.')
            return redirect('core:project-detail', pk=project_id)
        existing = FormRecord.objects.filter(
            project=project, form_definition=form_def,
        ).only('pk').first()
        if existing:
            messages.info(request, 'A record already exists for this form. Opening existing record.')
            return redirect('core:form-record-detail', pk=existing.pk)
        ctx = _form_record_context(request, project, form_def, None)
        return render(request, _form_template_name(form_def), ctx)

    def post(self, request, project_id, form_id):
        project = get_object_or_404(
            Project.objects.select_related(
                'manager', 'manager__managed_company', 'manager__company',
                'package_instance', 'package_instance__authorization',
            ),
            pk=project_id,
        )
        form_def = get_object_or_404(FormDefinition, pk=form_id)
        if not can_create_form_record(request.user, project, form_def):
            return redirect('core:project-detail', pk=project_id)
        form = FormRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.project = project
            record.form_definition = form_def
            record.created_by_user = request.user
            record.created_by_name = request.user.get_full_name() or request.user.username
            record.data = _build_record_data(request.POST, project=project, form_def=form_def)
            record.save()
            messages.success(request, 'Form record created.')
            return redirect('core:form-record-detail', pk=record.pk)
        ctx = _form_record_context(request, project, form_def, None, form=form)
        return render(request, _form_template_name(form_def), ctx)


class FormRecordDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        record = _get_form_record(pk)
        if not can_access_form(request.user, record.project, record.form_definition):
            return redirect('core:dashboard')
        other_data = dict(record.data or {})
        other_data.pop('table_cells', None)
        display_sections = _table_sections_for_record(
            record.form_definition, record, sparse=True,
        )
        company = company_for_project(record.project)
        return render(request, 'core/form_record_detail.html', {
            'record': record,
            'company': company,
            'form_owner': _form_owner_label(company, record.project),
            'reviews': list(record.reviews.filter(approved=True)),
            'can_edit': record.can_edit(request.user),
            'can_submit': record.can_submit(request.user),
            'can_review': record.can_review(request.user),
            'can_finalize': record.can_finalize(request.user),
            'table_sections': display_sections,
            'other_data': other_data,
        })


class FormRecordEditView(LoginRequiredMixin, View):
    def get(self, request, pk):
        record = _get_form_record(pk)
        if not record.can_edit(request.user):
            messages.error(request, 'Cannot edit this form.')
            return redirect('core:form-record-detail', pk=pk)
        ctx = _form_record_context(request, record.project, record.form_definition, record)
        return render(request, _form_template_name(record.form_definition), ctx)

    def post(self, request, pk):
        record = _get_form_record(pk)
        if not record.can_edit(request.user):
            return redirect('core:form-record-detail', pk=pk)
        form = FormRecordForm(request.POST, instance=record)
        if form.is_valid():
            record = form.save(commit=False)
            record.data = _build_record_data(
                request.POST, form_def=record.form_definition, existing_data=record.data,
            )
            record.save()
            messages.success(request, 'Form saved.')
            return redirect('core:form-record-detail', pk=record.pk)
        ctx = _form_record_context(request, record.project, record.form_definition, record, form=form)
        return render(request, _form_template_name(record.form_definition), ctx)


class FormSubmitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        record = get_object_or_404(FormRecord, pk=pk)
        if not record.can_submit(request.user):
            messages.error(request, 'You cannot submit this form.')
            return redirect('core:form-record-detail', pk=pk)
        record.status = 'submitted'
        record.submitted_at = timezone.now()
        record.save()
        seniors = TeamMember.objects.filter(
            project=record.project, role='senior_reviewer', is_active=True
        ).select_related('user')
        for tm in seniors:
            if tm.user:
                notify_user(
                    tm.user,
                    f'Form {record.form_definition.code} submitted for review by {record.created_by_name}.',
                    sender=request.user,
                    link=reverse('core:form-record-detail', args=[pk]),
                )
        notify_user(
            record.project.manager,
            f'Form {record.form_definition.code} submitted for review by {record.created_by_name}.',
            sender=request.user,
            link=reverse('core:form-record-detail', args=[pk]),
        )
        messages.success(request, 'Form submitted for senior review.')
        return redirect('core:form-record-detail', pk=pk)


class FormReviewView(LoginRequiredMixin, View):
    def post(self, request, pk):
        record = get_object_or_404(FormRecord, pk=pk)
        action = request.POST.get('action')
        if action == 'approve' and record.can_review(request.user):
            order = record.reviews.filter(approved=True).count() + 1
            if order <= 3:
                tm = get_team_member(request.user, record.project)
                role_label = tm.get_role_display() if tm else (request.user.designation or 'Senior Reviewer')
                position = tm.name if tm else request.user.get_full_name()
                FormReview.objects.create(
                    form_record=record,
                    reviewer=request.user,
                    reviewer_name=position,
                    reviewer_role=role_label,
                    review_order=order,
                    approved=True,
                )
                if record.status == 'submitted':
                    record.status = 'approved'
                    record.save()
                messages.success(request, f'Review {order} recorded.')
        elif action == 'return' and record.can_review(request.user):
            record.status = 'returned'
            record.save()
            if record.created_by_user:
                notify_user(
                    record.created_by_user,
                    f'Form {record.form_definition.code} returned for editing.',
                    sender=request.user,
                    link=reverse('core:form-record-detail', args=[pk]),
                )
            messages.info(request, 'Form returned to team member for editing.')
        return redirect('core:form-record-detail', pk=pk)


class FormFinalizeView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        record = get_object_or_404(FormRecord, pk=pk)
        if not record.can_finalize(request.user):
            return redirect('core:form-record-detail', pk=pk)
        record.status = 'finalized'
        record.finalized_by = request.user
        record.finalized_by_name = request.user.get_full_name()
        record.finalized_at = timezone.now()
        record.save()
        messages.success(request, 'Form finalized.')
        return redirect('core:form-record-detail', pk=pk)


# --- Public Form Access (F-02-IRR customer inquiry) ---
class PublicFormView(View):
    def get(self, request, token):
        if token == 'new':
            project_id = request.GET.get('project')
            form_id = request.GET.get('form')
            if project_id and form_id:
                project = get_object_or_404(Project, pk=project_id)
                form_def = get_object_or_404(FormDefinition, pk=form_id)
                if not form_def.is_public:
                    raise Http404
                record, _ = FormRecord.objects.get_or_create(
                    project=project,
                    form_definition=form_def,
                    defaults={'created_by_name': 'Customer', 'data': {}},
                )
                return redirect('core:public-form', token=str(record.pk))
            raise Http404
        record = get_object_or_404(FormRecord, pk=token)
        if not record.form_definition.is_public:
            raise Http404
        return render(request, 'core/public_form.html', {'record': record, 'form_def': record.form_definition})

    def post(self, request, token):
        record = get_object_or_404(FormRecord, pk=token)
        if not record.form_definition.is_public:
            raise Http404
        record.data = _parse_form_data(request.POST)
        record.save()
        notify_user(record.project.manager, f'Customer submitted {record.form_definition.code}.',
                    link=reverse('core:form-record-detail', args=[record.pk]))
        return render(request, 'core/public_form_submitted.html', {'record': record})


# --- Project Email Access ---
class ProjectAccessView(View):
    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        return render(request, 'core/project_access.html', {
            'form': ProjectAccessForm(), 'project': project,
        })

    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        form = ProjectAccessForm(request.POST)
        if form.is_valid():
            pwd = form.cleaned_data['password']
            vvb_pwd = project.vvb_password
            email = form.cleaned_data['email'].strip().lower()
            member = TeamMember.objects.filter(
                project=project, email__iexact=email, is_active=True
            ).select_related('user').first()
            if member and pwd in (project.access_password, vvb_pwd):
                user = member.user
                if not user:
                    user, _ = CustomUser.objects.get_or_create(
                        email=member.email,
                        defaults={
                            'username': member.email.split('@')[0][:30],
                            'user_type': 'employee',
                        },
                    )
                    member.user = user
                    member.save()
                user.set_password(pwd)
                user.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                request.session[f'project_access_{project_id}'] = email
                messages.success(request, f'Welcome, {member.name}. You can now access your project package.')
                return redirect('core:project-detail', pk=project_id)
            messages.error(request, 'Invalid email or password.')
        return render(request, 'core/project_access.html', {'form': form, 'project': project})


# --- Notifications ---
class NotificationsListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'core/notifications_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        n = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
        n.read = True
        n.save(update_fields=['read'])
        invalidate_notification_cache(request.user.pk)
        if n.link:
            return redirect(n.link)
        return redirect('core:notifications-list')


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, read=False).update(read=True)
        invalidate_notification_cache(request.user.pk)
        return redirect('core:notifications-list')


class DeleteNotificationView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        Notification.objects.filter(pk=notification_id, recipient=request.user).delete()
        return redirect('core:notifications-list')


def _sync_library_document_access(doc):
    """Sync library document visibility across package authorizations."""
    from .models import AuthorizedLibraryDocument

    if not doc.allowed_companies.exists():
        for auth in PackageAuthorization.objects.all():
            AuthorizedLibraryDocument.objects.update_or_create(
                authorization=auth,
                library_document=doc,
                defaults={'is_active': True},
            )
        return

    allowed_manager_ids = set(
        doc.allowed_companies.filter(
            authorized_manager__isnull=False,
        ).values_list('authorized_manager_id', flat=True)
    )
    for auth in PackageAuthorization.objects.all():
        AuthorizedLibraryDocument.objects.update_or_create(
            authorization=auth,
            library_document=doc,
            defaults={'is_active': auth.manager_id in allowed_manager_ids},
        )


# --- Helpers ---
def _form_template_name(form_def):
    code = form_def.code
    if code == 'F-01C-MRC':
        return 'core/forms/f01c_mrc.html'
    if code == 'F-02-IRR':
        return 'core/forms/f02_irr.html'
    if 'CALC' in code:
        return 'core/forms/calc_form.html'
    return 'core/form_record_form.html'


def _form_owner_label(company, project):
    if company and company.designated_person:
        return f'VVB, {company.designated_person}'
    if project and project.manager:
        name = project.manager.get_full_name() or project.manager.username
        return f'VVB, {name}'
    return 'VVB'


def _table_sections_for_record(form_def, record=None, sparse=False):
    layouts = list(FormTableLayout.objects.filter(form_definition=form_def).order_by('table_number', 'pk'))
    data = (record.data or {}) if record else {}
    sections = []
    for layout in layouts:
        stored = stored_cells_for_layout(data, layout, layouts)
        cells = _default_table_cells(layout, stored)
        lookup = layout.dropdown_lookup()
        headers, rows = _active_table_render(layout, cells, sparse=sparse, lookup=lookup)
        option_maps = {
            str(col_idx): cfg['option_map']
            for col_idx, configs in lookup.items()
            for cfg in configs
            if cfg.get('option_map')
        }
        sections.append({
            'layout': layout,
            'table_headers': headers,
            'table_rows': rows,
            'option_maps': option_maps,
            'option_maps_script_id': f'table-option-maps-{layout.pk}',
        })
    return sections


def _form_record_context(request, project, form_def, record, form=None):
    company = company_for_project(project)
    table_sections = _table_sections_for_record(form_def, record)
    ctx = {
        'form': form or FormRecordForm(instance=record),
        'project': project,
        'form_def': form_def,
        'record': record,
        'company': company,
        'form_owner': _form_owner_label(company, project),
        'reviews': list(record.reviews.filter(approved=True)) if record else [],
        'table_sections': table_sections,
    }
    # Only load global dropdown lists for templates that render them.
    code = form_def.code
    if code in ('F-01C-MRC', 'F-02-IRR') or 'CALC' in code:
        ctx['dropdown_lists'] = []
    else:
        ctx['dropdown_lists'] = list(DropdownList.objects.prefetch_related('options'))
    if code == 'F-01C-MRC':
        ctx['employees'] = list(EmployeeRecord.objects.filter(manager_id=project.manager_id))
    return ctx


def _can_access_project(user, project, session=None):
    return can_access_project(user, project, session)


def _project_header_data(project):
    """Snapshot project metadata on new form records."""
    return {
        'project_number': project.project_number,
        'client_name': project.company_name,
        'client_contact': project.client_contact or '',
        'facility': project.location,
        'report_type': project.report_type,
        'phase': project.phase,
        'phase_display': project.get_phase_display() if project.phase else '',
        'document_type': project.document_type,
        'document_type_display': project.get_document_type_display() if project.document_type else '',
        'engagement_year': project.engagement_year or '',
        'year': project.year,
        'report_type_year': (
            f'{project.report_type}-{project.year}'
            if project.report_type and project.year
            else project.report_type or str(project.year or '')
        ),
    }


def _row_has_content(row):
    return any(str(cell or '').strip() for cell in (row or []))


def _active_table_render(layout, cells, sparse=False, lookup=None):
    """Prepare active-only headers and rows (with original column indices) for templates."""
    active = layout.active_columns()
    headers = [column['label'] for _, column in active]
    lookup = lookup if lookup is not None else layout.dropdown_lookup()
    rows = []
    for row_idx, row in enumerate(cells or []):
        if sparse and not _row_has_content(row):
            continue
        row_cells = []
        for col_idx, _ in active:
            row_cells.append({
                'row': row_idx,
                'col': col_idx,
                'value': row[col_idx] if col_idx < len(row) else '',
                'dropdown': layout.dropdown_for_cell(row_idx, col_idx, lookup=lookup),
            })
        rows.append(row_cells)
    if sparse and not rows and cells:
        # Keep one blank row so empty tables still show structure.
        rows.append([
            {
                'row': 0,
                'col': col_idx,
                'value': '',
                'dropdown': layout.dropdown_for_cell(0, col_idx, lookup=lookup),
            }
            for col_idx, _ in active
        ])
    return headers, rows


def _default_table_cells(layout, stored=None):
    """Build a row/column grid for a table layout, optionally from saved data."""
    cols = len(layout.normalized_columns())
    rows = layout.row_count
    cells = [['' for _ in range(cols)] for _ in range(rows)]
    if stored:
        for r in range(min(rows, len(stored))):
            row = stored[r]
            if not isinstance(row, (list, tuple)):
                continue
            for c in range(min(cols, len(row))):
                cells[r][c] = row[c]
    return cells


def _parse_table_cells_from_post(post, layout, allow_legacy=False):
    """Read editable table cell values submitted by managers."""
    cells = _default_table_cells(layout)
    prefix = f'table_cell_{layout.pk}_'
    legacy_prefix = 'table_cell_'
    for key, value in post.items():
        if key.startswith(prefix):
            parts = key.split('_')
            if len(parts) < 5:
                continue
            try:
                row_idx = int(parts[3])
                col_idx = int(parts[4])
            except ValueError:
                continue
        elif allow_legacy and key.startswith(legacy_prefix):
            parts = key.split('_')
            if len(parts) < 4:
                continue
            try:
                row_idx = int(parts[2])
                col_idx = int(parts[3])
            except ValueError:
                continue
        else:
            continue
        if 0 <= row_idx < layout.row_count and 0 <= col_idx < len(layout.normalized_columns()):
            cells[row_idx][col_idx] = value
    from core.form_table_utils import validate_table_cells
    return validate_table_cells(layout, cells)


def _build_record_data(post, project=None, form_def=None, existing_data=None):
    """Merge project snapshot, notes, dropdowns, and optional admin table cells."""
    data = dict(existing_data or {})
    if project and not existing_data:
        data.update(_project_header_data(project))
    data.update(_parse_form_data(post))
    if form_def:
        layouts = list(FormTableLayout.objects.filter(form_definition=form_def).order_by('table_number', 'pk'))
        if layouts:
            allow_legacy = len(layouts) == 1
            table_cells = {
                str(layout.pk): _parse_table_cells_from_post(post, layout, allow_legacy=allow_legacy)
                for layout in layouts
            }
            data['table_cells'] = table_cells
    return data


def _parse_form_data(post):
    data = {}
    skip = {'csrfmiddlewaretoken', 'created_by_name', 'notes', 'return'}
    for key, value in post.items():
        if key in skip or key.startswith('table_cell_'):
            continue
        if key.startswith('field_'):
            data[key[6:]] = value
        elif key not in ('action',):
            data[key] = value
    notes = post.get('notes', '')
    if notes:
        data['notes'] = notes
    return data
