from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from django.utils import timezone
from .models import (
    CustomUser, Company, PackageTemplate, PackageAuthorization, AuthorizedForm,
    LibraryDocument, DropdownList, DropdownOption, Project, TeamMember,
    EmployeeRecord, FormRecord, FormDefinition, USER_TYPE_CHOICES, TEAM_ROLE_CHOICES,
    LIBRARY_CATEGORY_CHOICES, PROJECT_PHASE_CHOICES, PROJECT_DOCUMENT_TYPE_CHOICES,
    FORM_TYPE_CHOICES, FORM_TYPE_TO_CATEGORY, USER_ROLE_CHOICES,
)
import os
import re


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your password'})
    )


class ProjectAccessForm(forms.Form):
    """Email + password access for authorized team members."""
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class AdminRegistrationForm(UserCreationForm):
    """Registration for admin users."""
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'}),
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.user_type = 'admin'
        if self.user:
            user.created_by = self.user
        if commit:
            user.save()
        return user


class AdminUserEditForm(forms.ModelForm):
    """Admin account edit — username, email, active status."""
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = CustomUser.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email


class AdminSelfProfileForm(forms.ModelForm):
    """Admin editing their own profile."""
    class Meta:
        model = CustomUser
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = CustomUser.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    designation = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    contact_number = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    under_supervision = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(user_type='manager'),
        required=False, widget=forms.Select(attrs={'class': 'form-control'})
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(), required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    username = forms.CharField(required=False, widget=forms.HiddenInput())
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'user_type',
                  'designation', 'contact_number', 'under_supervision', 'company',
                  'password1', 'password2']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            if self.user.user_type == 'admin':
                self.fields['user_type'].choices = [('admin', 'Admin')]
                self.fields['user_type'].initial = 'admin'
            elif self.user.user_type == 'manager':
                self.fields['user_type'].choices = [('employee', 'Employee')]
                self.fields['under_supervision'].queryset = CustomUser.objects.filter(id=self.user.id)
                self.fields['under_supervision'].initial = self.user
                self.fields['company'].widget = forms.HiddenInput()
        user_type = self.data.get('user_type') or self.initial.get('user_type')
        if user_type == 'admin':
            self.fields['under_supervision'].widget = forms.HiddenInput()
            self.fields['company'].widget = forms.HiddenInput()
        elif user_type == 'manager':
            self.fields['under_supervision'].required = False

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        if email:
            cleaned['username'] = re.sub(r'[^a-zA-Z0-9]', '', email.split('@')[0])[:30]
            base = cleaned['username']
            counter = 1
            while CustomUser.objects.filter(username=cleaned['username']).exists():
                cleaned['username'] = f'{base}{counter}'
                counter += 1
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['username']
        if self.user:
            user.created_by = self.user
        if commit:
            user.save()
        return user


MANAGER_USER_TYPE_CHOICES = [
    ('manager', 'Manager'),
    ('employee', 'Employee'),
]


def _unique_username_from_email(email, exclude_pk=None):
    """Derive a unique username from an email when managers create users."""
    base = (email.split('@')[0] if email else 'user').strip()[:150] or 'user'
    username = base
    counter = 1
    while True:
        qs = CustomUser.objects.filter(username=username)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return username
        suffix = str(counter)
        username = f"{base[: max(1, 150 - len(suffix))]}{suffix}"
        counter += 1


class ManagerRegistrationForm(UserCreationForm):
    """Managers create team member accounts (role/designation are set per project)."""
    full_name = forms.CharField(
        required=True,
        label='Full Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'}),
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields.pop('username', None)

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not full_name:
            raise forms.ValidationError('Full name is required.')
        return full_name

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data['full_name']
        parts = full_name.split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        user.email = self.cleaned_data['email']
        user.username = _unique_username_from_email(user.email)
        user.user_type = 'employee'
        if self.user:
            user.created_by = self.user
            user.under_supervision = self.user
            if self.user.company_id:
                user.company_id = self.user.company_id
        if commit:
            user.save()
        return user


class ManagerUserEditForm(forms.ModelForm):
    """Edit manager/employee accounts — managers cannot change users to admin."""
    full_name = forms.CharField(
        required=True,
        label='Full Name',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['full_name'].initial = self.instance.get_full_name()

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not full_name:
            raise forms.ValidationError('Full name is required.')
        return full_name

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = CustomUser.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        parts = self.cleaned_data['full_name'].split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
        return user


class UserProfileEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'contact_number']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'contact_number': 'Contact',
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = CustomUser.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = CustomUser.objects.filter(username=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this username already exists.')
        return username


class AdminSetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password'}),
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password1') != cleaned.get('new_password2'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned


class SelfPasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password',
        }),
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password',
        }),
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if old_password and not self.user.check_password(old_password):
            raise forms.ValidationError('Current password is incorrect.')
        return old_password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password1') != cleaned.get('new_password2'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned


class CompanyForm(forms.ModelForm):
    manager_username = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    manager_password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    manager_email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    manager_first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    manager_last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Company
        fields = ['name', 'location', 'abbreviation']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_manager = None
        if self.instance and self.instance.pk and self.instance.authorized_manager:
            mgr = self.instance.authorized_manager
            self.fields['manager_email'].initial = mgr.email
            self.fields['manager_username'].initial = mgr.username
            self.fields['manager_first_name'].initial = mgr.first_name
            self.fields['manager_last_name'].initial = mgr.last_name

    def clean_manager_email(self):
        email = self.cleaned_data.get('manager_email', '').strip()
        if not email:
            return email
        existing = CustomUser.objects.filter(email__iexact=email).first()
        if existing:
            if existing.user_type != 'manager':
                raise forms.ValidationError(
                    f'A user with this email already exists as {existing.get_user_type_display()}.'
                )
            other_company = Company.objects.filter(authorized_manager=existing)
            if self.instance and self.instance.pk:
                other_company = other_company.exclude(pk=self.instance.pk)
            if other_company.exists():
                company = other_company.first()
                raise forms.ValidationError(
                    f'This email is already the authorized manager for "{company.name}".'
                )
            self.existing_manager = existing
        return email

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('manager_email')
        if not email:
            return cleaned
        username = (cleaned.get('manager_username') or email.split('@')[0])[:150]
        qs = CustomUser.objects.filter(username=username)
        if self.existing_manager:
            qs = qs.exclude(pk=self.existing_manager.pk)
        if qs.exists():
            raise forms.ValidationError({
                'manager_username': f'Username "{username}" is already taken. Choose a different username.',
            })
        cleaned['manager_username'] = username
        return cleaned


FORM_CONTROL = {'class': 'form-control company-field-input'}
DATE_CONTROL = {'class': 'form-control company-field-input', 'type': 'date'}


class CompanyCreateForm(forms.Form):
    """Combined company + package authorization form for admin create."""
    name = forms.CharField(
        label='Name of Client', max_length=200,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    abbreviation = forms.CharField(
        label='Client Name Abbreviation', max_length=20,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    issue_date = forms.DateField(
        label='Issue Date', required=False,
        widget=forms.DateInput(attrs=DATE_CONTROL),
    )
    version = forms.CharField(
        label='Version', max_length=50, required=False,
        widget=forms.TextInput(attrs={**FORM_CONTROL, 'placeholder': 'e.g. 1st Issue, V1.0'}),
    )
    start_date = forms.DateField(
        label='Start Date',
        widget=forms.DateInput(attrs=DATE_CONTROL),
    )
    end_date = forms.DateField(
        label='End Date',
        widget=forms.DateInput(attrs=DATE_CONTROL),
    )
    project_limit = forms.IntegerField(
        label='Number of Project', min_value=1, initial=1,
        widget=forms.NumberInput(attrs={**FORM_CONTROL, 'min': 1}),
    )
    designated_person = forms.CharField(
        label='Designated Person', max_length=200, required=False,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    access_password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={**FORM_CONTROL, 'placeholder': 'Package access password'}),
    )
    project_manager_name = forms.CharField(
        label='Project Manager (Owner)', max_length=100,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    client_email = forms.EmailField(
        label='E-mail (Client)',
        widget=forms.EmailInput(attrs=FORM_CONTROL),
    )
    client_contact = forms.CharField(
        label='Contact of Client', max_length=200, required=False,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End Date must be on or after Start Date.')
        email = (cleaned.get('client_email') or '').strip()
        if email and CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError({
                'client_email': 'A user with this email already exists.',
            })
        if email:
            cleaned['manager_username'] = _unique_username_from_email(email)
        return cleaned

    def split_manager_name(self):
        parts = self.cleaned_data['project_manager_name'].strip().split(None, 1)
        first = parts[0] if parts else ''
        last = parts[1] if len(parts) > 1 else ''
        return first, last


class CompanyEditForm(CompanyCreateForm):
    """Edit company with package authorization and form selection."""

    access_password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(attrs={
            **FORM_CONTROL,
            'placeholder': 'Leave blank to keep current password',
        }),
    )

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def clean(self):
        cleaned = super(CompanyCreateForm, self).clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End Date must be on or after Start Date.')

        exclude_pk = self.company.authorized_manager_id if self.company else None
        email = (cleaned.get('client_email') or '').strip()
        if email:
            qs = CustomUser.objects.filter(email__iexact=email)
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            if qs.exists():
                raise forms.ValidationError({
                    'client_email': 'A user with this email already exists.',
                })
        if exclude_pk and self.company and self.company.authorized_manager:
            cleaned['manager_username'] = self.company.authorized_manager.username
        elif email:
            cleaned['manager_username'] = _unique_username_from_email(email)

        project_limit = cleaned.get('project_limit')
        if self.company and project_limit is not None:
            existing = self.company.manager_project_count()
            if project_limit < existing:
                raise forms.ValidationError({
                    'project_limit': (
                        f'Cannot set below {existing} — the manager has already created '
                        f'{existing} project(s).'
                    ),
                })
        return cleaned


def company_edit_initial(company, authorization):
    mgr = company.authorized_manager
    pm_name = ''
    if mgr:
        pm_name = (mgr.get_full_name() or '').strip() or mgr.username
    initial = {
        'name': company.name,
        'abbreviation': company.abbreviation,
        'issue_date': company.issue_date,
        'version': company.version,
        'designated_person': company.designated_person,
        'client_contact': company.client_contact,
        'client_email': company.client_email or (mgr.email if mgr else ''),
        'project_manager_name': pm_name,
        'project_limit': company.project_limit,
    }
    if authorization:
        initial.update({
            'start_date': authorization.start_date,
            'end_date': authorization.end_date,
        })
    return initial


def build_package_selection_rows(form_definitions):
    """Build row data for the 3-column package selection grid."""
    by_cat = {
        'master_record': [],
        'unlimited_use': [],
        'limited_form': [],
        'report': [],
    }
    for fd in form_definitions:
        cat = fd.category if fd.category in by_cat else 'limited_form'
        by_cat[cat].append(fd)

    col_master = [{'type': 'form', 'form': fd} for fd in by_cat['master_record']]
    if by_cat['unlimited_use']:
        col_master.append({'type': 'header', 'text': 'Unlimited Use'})
        col_master.extend({'type': 'form', 'form': fd} for fd in by_cat['unlimited_use'])

    limited = by_cat['limited_form']
    mid = (len(limited) + 1) // 2
    col_limited_1 = [{'type': 'form', 'form': fd} for fd in limited[:mid]]
    col_limited_2 = [{'type': 'form', 'form': fd} for fd in limited[mid:]]
    if by_cat['report']:
        col_limited_2.append({'type': 'header', 'text': 'Reports'})
        col_limited_2.extend({'type': 'form', 'form': fd} for fd in by_cat['report'])

    max_rows = max(len(col_master), len(col_limited_1), len(col_limited_2), 1)
    rows = []
    for i in range(max_rows):
        rows.append({
            'master': col_master[i] if i < len(col_master) else None,
            'limited1': col_limited_1[i] if i < len(col_limited_1) else None,
            'limited2': col_limited_2[i] if i < len(col_limited_2) else None,
        })
    return rows


class FormDetailsForm(forms.ModelForm):
    class Meta:
        model = FormDefinition
        fields = ['code', 'name', 'form_type', 'description']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'form_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].label = 'Form Number'
        self.fields['name'].label = 'Form Name'
        self.fields['form_type'].label = 'Form Type'
        self.fields['form_type'].choices = [('', '---------')] + list(FORM_TYPE_CHOICES)

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError('Form number is required.')
        return code

    def save(self, commit=True):
        form_def = super().save(commit=False)
        form_type = self.cleaned_data.get('form_type')
        if form_type:
            form_def.category = FORM_TYPE_TO_CATEGORY.get(form_type, 'limited_form')
        if commit:
            form_def.save()
        return form_def


class PackageTemplateForm(forms.ModelForm):
    class Meta:
        model = PackageTemplate
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PackageAuthorizationForm(forms.ModelForm):
    class Meta:
        model = PackageAuthorization
        fields = ['package_template', 'manager', 'vvb_name', 'abbreviation', 'year',
                  'start_date', 'end_date', 'package_count']
        widgets = {
            'package_template': forms.Select(attrs={'class': 'form-control'}),
            'manager': forms.Select(attrs={'class': 'form-control'}),
            'vvb_name': forms.TextInput(attrs={'class': 'form-control'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'package_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class AuthorizedFormToggleForm(forms.ModelForm):
    class Meta:
        model = AuthorizedForm
        fields = ['is_active']
        widgets = {'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})}


class LibraryDocumentForm(forms.ModelForm):
    ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}

    class Meta:
        model = LibraryDocument
        fields = ['title', 'category', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx'}),
        }

    def clean_file(self):
        uploaded = self.cleaned_data.get('file')
        if not uploaded:
            return uploaded
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                'Allowed file types: PDF, Word (.doc, .docx), PowerPoint (.ppt, .pptx), Excel (.xls, .xlsx).'
            )
        return uploaded


class DropdownListForm(forms.ModelForm):
    class Meta:
        model = DropdownList
        fields = ['name', 'slug', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class DropdownOptionForm(forms.ModelForm):
    class Meta:
        model = DropdownOption
        fields = ['value', 'order', 'is_active']
        widgets = {
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            'project_number', 'company_name', 'client_contact', 'location', 'report_type',
            'engagement_year', 'year', 'phase', 'document_type',
        ]
        widgets = {
            'project_number': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Enter your client's name",
            }),
            'client_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'report_type': forms.TextInput(attrs={'class': 'form-control'}),
            'engagement_year': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1900,
                'max': 2100,
            }),
            'phase': forms.Select(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project_number'].label = 'Project Number'
        self.fields['company_name'].label = 'Client Name'
        self.fields['client_contact'].label = 'Contact of Client'
        self.fields['client_contact'].required = False
        self.fields['location'].label = 'Facility & Jurisdiction'
        self.fields['report_type'].label = 'Report Type'
        self.fields['engagement_year'].label = 'Engagement'
        self.fields['year'].label = 'Year'
        self.fields['phase'].label = 'Phase'
        self.fields['document_type'].label = 'Document Type'
        self.fields['phase'].choices = [('', '---------')] + list(PROJECT_PHASE_CHOICES)
        self.fields['document_type'].choices = [('', '---------')] + list(PROJECT_DOCUMENT_TYPE_CHOICES)
        if not self.instance.pk:
            self.fields['year'].initial = timezone.now().year


class TeamMemberForm(forms.Form):
    """Authorize an existing user (created by the manager) onto a project."""
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        label='User',
        empty_label='--------- Select a user ---------',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    user_role = forms.ChoiceField(
        choices=[('', '---------')] + list(USER_ROLE_CHOICES),
        label='User Role',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    designation = forms.CharField(
        max_length=100,
        required=False,
        label='Designation',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter designation'}),
    )
    position_title = forms.CharField(
        max_length=150,
        required=False,
        label='Position Title',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter position title'}),
    )

    def __init__(self, *args, manager=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = CustomUser.objects.filter(user_type='employee', is_active=True)
        if manager is not None:
            queryset = queryset.filter(created_by=manager)
        self.fields['user'].queryset = queryset.order_by('first_name', 'last_name', 'username')

    def clean_user(self):
        user = self.cleaned_data.get('user')
        if user and not user.is_active:
            raise forms.ValidationError('This user is inactive and cannot be authorized.')
        return user


class TeamMemberEditForm(forms.ModelForm):
    """Edit an authorized member's role/designation/position for a specific project."""
    user_role = forms.ChoiceField(
        choices=[('', '---------')] + list(USER_ROLE_CHOICES),
        label='User Role',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = TeamMember
        fields = ['user_role', 'designation', 'position_title']
        widgets = {
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter designation'}),
            'position_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter position title'}),
        }

    def clean_user_role(self):
        user_role = self.cleaned_data.get('user_role')
        if not user_role:
            raise forms.ValidationError('Select a user role.')
        return user_role


class EmployeeRecordForm(forms.ModelForm):
    class Meta:
        model = EmployeeRecord
        fields = ['name', 'email', 'contact_number', 'position', 'designation', 'role', 'cv']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.TextInput(attrs={'class': 'form-control'}),
            'cv': forms.FileInput(attrs={'class': 'form-control'}),
        }


class FormRecordForm(forms.ModelForm):
    """Generic form record — creator name is set automatically from the logged-in user."""

    class Meta:
        model = FormRecord
        fields = []


class CVApprovalForm(forms.ModelForm):
    class Meta:
        model = EmployeeRecord
        fields = ['cv_approval_status']
        widgets = {
            'cv_approval_status': forms.Select(attrs={'class': 'form-control'}),
        }


class FormTableLayoutForm(forms.Form):
    table_number = forms.IntegerField(
        min_value=1,
        initial=1,
        label='Number of Table',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    table_name = forms.CharField(
        required=False,
        label='Name of Table',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter table name'}),
    )
    notes = forms.CharField(
        required=False,
        label='Table Notes',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notes related to this table'}),
    )
    row_count = forms.IntegerField(
        min_value=1,
        initial=100,
        label='Number of Rows',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )


class ViewPackageSearchForm(forms.Form):
    vvb_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name of VVB'})
    )
