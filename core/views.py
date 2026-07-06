from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import FileResponse, Http404
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.views import View
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
import json
from urllib.parse import quote

from .models import (
    CustomUser, Company, PackageTemplate, PackageAuthorization, PackageInstance,
    AuthorizedForm, LibraryDocument, DropdownList, DropdownOption, Project,
    TeamMember, EmployeeRecord, FormRecord, FormReview, FormDefinition,
    SubPackage, Notification, notify_user, FORM_TYPE_CHOICES,
)
from .forms import (
    EmailLoginForm, UserRegistrationForm, AdminRegistrationForm, AdminUserEditForm,
    AdminSelfProfileForm, ManagerRegistrationForm, ManagerUserEditForm, UserProfileEditForm, AdminSetPasswordForm,
    CompanyForm, PackageAuthorizationForm, LibraryDocumentForm,
    CompanyCreateForm, CompanyEditForm, company_edit_initial,
    DropdownListForm, DropdownOptionForm, ProjectForm, TeamMemberForm,
    EmployeeRecordForm, FormRecordForm, CVApprovalForm, ViewPackageSearchForm,
    ProjectAccessForm, FormDetailsForm,
)
from .access import (
    can_access_project, can_access_form, can_create_form_record,
    can_access_library_document, get_authorized_library_documents,
    get_employee_projects, get_team_member, can_view_report, get_manager_manageable_users,
    company_for_project,
)
from .permissions import AdminRequiredMixin, ManagerRequiredMixin, EmployeeBlockedMixin, ManagerOrAdminMixin


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
    def get(self, request):
        user = request.user
        ctx = {'user': user}
        if user.user_type == 'admin':
            ctx.update({
                'admin_count': CustomUser.objects.filter(user_type='admin').count(),
                'manager_count': CustomUser.objects.filter(user_type='manager').count(),
                'employee_count': CustomUser.objects.filter(user_type='employee').count(),
                'company_count': Company.objects.count(),
                'authorization_count': PackageAuthorization.objects.count(),
                'form_details_count': FormDefinition.objects.count(),
                'library_count': LibraryDocument.objects.count(),
            })
        elif user.user_type == 'manager':
            projects = Project.objects.filter(manager=user)
            company = _manager_company(user)
            auth = PackageAuthorization.objects.filter(manager=user).order_by('-created_at').first()
            ctx.update({
                'projects': projects[:5],
                'project_count': projects.count(),
                'total_projects_allocated': company.project_limit if company else 0,
                'remaining_projects': company.projects_remaining() if company else 0,
                'allocated_forms_count': (
                    AuthorizedForm.objects.filter(authorization=auth, is_active=True).count()
                    if auth else 0
                ),
                'team_member_count': TeamMember.objects.filter(
                    project__manager=user, is_active=True
                ).count(),
                'pending_reviews': FormRecord.objects.filter(
                    project__manager=user, status='submitted'
                ).count(),
            })
        else:
            assignments = get_employee_projects(user)
            team_projects = [a.project for a in assignments]
            ctx.update({
                'projects': team_projects,
                'assignments': assignments,
                'form_count': FormRecord.objects.filter(created_by_user=user).count(),
                'pending_forms': FormRecord.objects.filter(
                    created_by_user=user, status__in=['draft', 'returned']
                ).count(),
                'library_count': get_authorized_library_documents(user).count(),
            })
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
            messages.success(request, f'User {display_name} created successfully.')
            return redirect('core:users')
        return render(request, 'core/reg_form.html', {
            'form': form,
            'creating_admin': creating_admin,
        })


class UsersView(ManagerOrAdminMixin, View):
    def get(self, request):
        user = request.user
        search = request.GET.get('search', '').strip()
        user_type_filter = request.GET.get('user_type', '')
        designation_filter = request.GET.get('designation', '').strip()
        supervisor_filter = request.GET.get('supervisor', '').strip()
        active_filter = request.GET.get('active', '')

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
            if user_type_filter in ('manager', 'employee'):
                users = users.filter(user_type=user_type_filter)
            if designation_filter:
                users = users.filter(designation__icontains=designation_filter)
            if supervisor_filter:
                users = users.filter(
                    Q(under_supervision__first_name__icontains=supervisor_filter)
                    | Q(under_supervision__last_name__icontains=supervisor_filter)
                )
            if active_filter == 'active':
                users = users.filter(is_active=True)
            elif active_filter == 'inactive':
                users = users.filter(is_active=False)
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
            'user_type_filter': user_type_filter,
            'search_query': search,
            'designation_filter': designation_filter,
            'supervisor_filter': supervisor_filter,
            'active_filter': active_filter,
            'admin_users_only': user.user_type == 'admin',
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
        return render(request, 'core/user.html', {'user_view': profile})


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
            if request.user.user_type == 'admin' and target.user_type == 'admin':
                return admin_users_success_redirect('updated', updated.username)
            messages.success(request, 'User updated.')
            return redirect('core:user', profile_id=target.id)
        return render(request, 'core/edit_user_profile.html', {
            'form': form,
            'target_user': target,
            'editing_admin': request.user.user_type == 'admin' and target.user_type == 'admin',
        })


class UserDeleteView(LoginRequiredMixin, View):
    def get(self, request, pk):
        target = get_object_or_404(CustomUser, id=pk)
        if not request.user.can_manage_user(target) or target == request.user:
            messages.error(request, 'Cannot delete this user.')
            return redirect('core:users')
        if request.user.user_type == 'manager' and target.user_type == 'admin':
            messages.error(request, 'Managers cannot delete admin accounts.')
            return redirect('core:users')
        return render(request, 'core/delete_user.html', {'target_user': target})

    def post(self, request, pk):
        target = get_object_or_404(CustomUser, id=pk)
        if (
            request.user.can_manage_user(target)
            and target != request.user
            and not (request.user.user_type == 'manager' and target.user_type == 'admin')
        ):
            username = target.username
            is_admin = target.user_type == 'admin'
            target.delete()
            if is_admin:
                return admin_users_success_redirect('deleted', username)
            messages.success(request, 'User deleted.')
        return redirect('core:users')


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
        return {
            'form_definitions': [],
            'form_definition_groups': [],
            'package_template': None,
        }
    form_definitions = FormDefinition.objects.filter(
        sub_package__package_template=package_template,
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
        package_template = PackageTemplate.objects.filter(is_active=True).first()

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
            else PackageTemplate.objects.filter(is_active=True).first()
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
            else PackageTemplate.objects.filter(is_active=True).first()
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
            'manager_username': mgr.username if mgr else '',
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
    template = PackageTemplate.objects.filter(is_active=True).first()
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
        return FormDefinition.objects.select_related(
            'sub_package', 'sub_package__package_template',
        ).order_by('code')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
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
                    'No active package template found. Run seed_forms or create a package template first.',
                )
            else:
                form_def = form.save(commit=False)
                form_def.sub_package = sub_package
                form_def.order = sub_package.forms.count()
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
        form_def = get_object_or_404(FormDefinition, pk=pk)
        return render(request, 'core/form_details_form.html', {
            'form': FormDetailsForm(instance=form_def),
            'title': 'Edit Form Details',
            'form_def': form_def,
        })

    def post(self, request, pk):
        form_def = get_object_or_404(FormDefinition, pk=pk)
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
            doc.allowed_companies.set([form.cleaned_data['allowed_client']])
            _sync_library_document_access(doc)
            messages.success(request, 'Document uploaded to the Documents Library.')
            return redirect('core:library-list')
        return render(request, 'core/library_form.html', {'form': form, 'title': 'Upload Information'})


class LibraryDocumentDeleteView(AdminRequiredMixin, DeleteView):
    model = LibraryDocument
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('core:library-list')


class LibraryDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        doc = get_object_or_404(LibraryDocument, pk=pk)
        if not can_access_library_document(request.user, doc):
            messages.error(request, 'You are not authorized to access this document.')
            return redirect('core:dashboard')
        return FileResponse(doc.file.open(), as_attachment=True, filename=doc.file.name.split('/')[-1])


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
            messages.error(
                request,
                f'You have reached the maximum of {company.project_limit} project(s) allowed for your company.',
            )
            return redirect('core:project-list')
        form = ProjectForm()
        return render(request, 'core/project_form.html', {'form': form, 'title': 'Create Project'})

    def post(self, request):
        at_limit, company = _manager_at_project_limit(request.user)
        if at_limit:
            messages.error(
                request,
                f'You have reached the maximum of {company.project_limit} project(s) allowed for your company.',
            )
            return redirect('core:project-list')
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
            messages.success(request, f'Project {project.project_number} created. Access password: {project.access_password}')
            return redirect('core:project-detail', pk=project.pk)
        return render(request, 'core/project_form.html', {'form': form, 'title': 'Create Project'})


class ProjectDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        if not can_access_project(request.user, project, request.session):
            messages.error(request, 'Access denied.')
            return redirect('core:dashboard')
        auth = project.package_instance.authorization
        template = auth.package_template
        active_form_ids = AuthorizedForm.objects.filter(
            authorization=auth, is_active=True
        ).values_list('form_definition_id', flat=True)
        sub_packages = []
        records = FormRecord.objects.filter(project=project).select_related('form_definition')
        record_by_form = {r.form_definition_id: r for r in records}
        report_records = []
        for sub in template.sub_packages.prefetch_related('forms'):
            form_rows = []
            for f in sub.forms.all():
                if f.id in active_form_ids:
                    rec = record_by_form.get(f.id)
                    form_rows.append({'form_def': f, 'record': rec})
                    if rec and can_view_report(request.user, rec):
                        report_records.append(rec)
            if form_rows:
                sub_packages.append({'sub_package': sub, 'form_rows': form_rows})
        team_member = get_team_member(request.user, project)
        return render(request, 'core/project_detail.html', {
            'project': project,
            'sub_packages': sub_packages,
            'team_members': project.team_members.filter(is_active=True),
            'vvb_password': auth.access_password,
            'team_member': team_member,
            'can_authorize_library': get_authorized_library_documents(request.user).exists(),
            'report_records': report_records,
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
            messages.success(request, 'Project updated.')
            return redirect('core:project-detail', pk=project.pk)
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
    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id, manager=request.user)
        return render(request, 'core/team_member_form.html', {'form': TeamMemberForm(), 'project': project})

    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id, manager=request.user)
        form = TeamMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.project = project
            user, _ = CustomUser.objects.get_or_create(
                email=member.email,
                defaults={
                    'username': member.email.split('@')[0][:30],
                    'first_name': member.name.split()[0] if member.name else '',
                    'last_name': ' '.join(member.name.split()[1:]) if len(member.name.split()) > 1 else '',
                    'user_type': 'employee',
                }
            )
            pwd = project.vvb_password
            user.set_password(pwd)
            user.save()
            member.user = user
            member.save()
            access_url = request.build_absolute_uri(reverse('core:project-access', args=[project.pk]))
            notify_user(
                user,
                f'You are authorized for project {project.project_number}. '
                f'Email: {member.email} | Password: {project.vvb_password} | '
                f'Access: {access_url}',
                sender=request.user,
                link=reverse('core:project-access', args=[project.pk]),
            )
            messages.success(request, f'{member.name} authorized. Notification sent.')
            return redirect('core:project-detail', pk=project.pk)
        return render(request, 'core/team_member_form.html', {'form': form, 'project': project})


class TeamMemberDeleteView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk, project__manager=request.user)
        project_id = member.project_id
        member.is_active = False
        member.save()
        messages.success(request, 'Team member removed.')
        return redirect('core:project-detail', pk=project_id)


# --- Form Records & Workflow ---
class FormRecordCreateView(LoginRequiredMixin, View):
    def get(self, request, project_id, form_id):
        project = get_object_or_404(Project, pk=project_id)
        form_def = get_object_or_404(FormDefinition, pk=form_id)
        if not can_create_form_record(request.user, project, form_def):
            messages.error(request, 'You are not authorized to create this form record.')
            return redirect('core:project-detail', pk=project_id)
        if FormRecord.objects.filter(project=project, form_definition=form_def).exists():
            messages.info(request, 'A record already exists for this form. Opening existing record.')
            record = FormRecord.objects.get(project=project, form_definition=form_def)
            return redirect('core:form-record-detail', pk=record.pk)
        ctx = _form_record_context(request, project, form_def, None)
        return render(request, _form_template_name(form_def), ctx)

    def post(self, request, project_id, form_id):
        project = get_object_or_404(Project, pk=project_id)
        form_def = get_object_or_404(FormDefinition, pk=form_id)
        if not can_create_form_record(request.user, project, form_def):
            return redirect('core:project-detail', pk=project_id)
        form = FormRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.project = project
            record.form_definition = form_def
            record.created_by_user = request.user
            record.data = {**_project_header_data(project), **_parse_form_data(request.POST)}
            record.save()
            messages.success(request, 'Form record created.')
            return redirect('core:form-record-detail', pk=record.pk)
        ctx = _form_record_context(request, project, form_def, None, form=form)
        return render(request, _form_template_name(form_def), ctx)


class FormRecordDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        record = get_object_or_404(FormRecord, pk=pk)
        if not can_access_form(request.user, record.project, record.form_definition):
            return redirect('core:dashboard')
        return render(request, 'core/form_record_detail.html', {
            'record': record,
            'company': company_for_project(record.project),
            'form_owner': _form_owner_label(company_for_project(record.project), record.project),
            'reviews': record.reviews.filter(approved=True),
            'can_edit': record.can_edit(request.user),
            'can_submit': record.can_submit(request.user),
            'can_review': record.can_review(request.user),
            'can_finalize': record.can_finalize(request.user),
        })


class FormRecordEditView(LoginRequiredMixin, View):
    def get(self, request, pk):
        record = get_object_or_404(FormRecord, pk=pk)
        if not record.can_edit(request.user):
            messages.error(request, 'Cannot edit this form.')
            return redirect('core:form-record-detail', pk=pk)
        ctx = _form_record_context(request, record.project, record.form_definition, record)
        return render(request, _form_template_name(record.form_definition), ctx)

    def post(self, request, pk):
        record = get_object_or_404(FormRecord, pk=pk)
        if not record.can_edit(request.user):
            return redirect('core:form-record-detail', pk=pk)
        form = FormRecordForm(request.POST, instance=record)
        if form.is_valid():
            record = form.save(commit=False)
            record.data = _parse_form_data(request.POST)
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
        n.save()
        if n.link:
            return redirect(n.link)
        return redirect('core:notifications-list')


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, read=False).update(read=True)
        return redirect('core:notifications-list')


class DeleteNotificationView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        Notification.objects.filter(pk=notification_id, recipient=request.user).delete()
        return redirect('core:notifications-list')


def _sync_library_document_access(doc):
    """Activate library access only for package authorizations of selected clients."""
    from .models import AuthorizedLibraryDocument
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


def _form_record_context(request, project, form_def, record, form=None):
    company = company_for_project(project)
    return {
        'form': form or FormRecordForm(
            instance=record,
            initial=None if record else {'created_by_name': request.user.get_full_name()},
        ),
        'project': project,
        'form_def': form_def,
        'record': record,
        'company': company,
        'form_owner': _form_owner_label(company, project),
        'dropdown_lists': DropdownList.objects.prefetch_related('options'),
        'reviews': record.reviews.filter(approved=True) if record else [],
    }


def _can_access_project(user, project, session=None):
    return can_access_project(user, project, session)


def _project_header_data(project):
    """Snapshot project metadata on new form records."""
    return {
        'project_number': project.project_number,
        'client_name': project.company_name,
        'facility': project.location,
        'report_type': project.report_type,
        'phase': project.phase,
        'phase_display': project.get_phase_display() if project.phase else '',
        'document_type': project.document_type,
        'document_type_display': project.get_document_type_display() if project.document_type else '',
        'engagement_year': project.engagement_year or str(project.year),
    }


def _parse_form_data(post):
    data = {}
    skip = {'csrfmiddlewaretoken', 'created_by_name', 'notes'}
    for key, value in post.items():
        if key in skip:
            continue
        if key.startswith('field_'):
            data[key[6:]] = value
        elif key not in ('action',):
            data[key] = value
    notes = post.get('notes', '')
    if notes:
        data['notes'] = notes
    return data
