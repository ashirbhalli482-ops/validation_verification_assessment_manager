from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from .models import (
    CustomUser, Company, PackageTemplate, PackageAuthorization, AuthorizedForm,
    LibraryDocument, DropdownList, DropdownOption, Project, TeamMember,
    EmployeeRecord, FormRecord, USER_TYPE_CHOICES, TEAM_ROLE_CHOICES,
    LIBRARY_CATEGORY_CHOICES,
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


class ManagerRegistrationForm(UserCreationForm):
    """Managers create manager or employee accounts (not admin)."""
    user_type = forms.ChoiceField(
        choices=MANAGER_USER_TYPE_CHOICES,
        label='User type',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    username = forms.CharField(
        max_length=150,
        required=True,
        label='User name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}),
    )
    designation = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter designation'}),
    )
    under_supervision = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        label='Under supervision',
        widget=forms.Select(attrs={'class': 'form-control'}),
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
        fields = [
            'user_type', 'username', 'designation', 'under_supervision',
            'email', 'password1', 'password2',
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['under_supervision'].queryset = CustomUser.objects.filter(
                user_type='manager',
            ).filter(
                Q(created_by=self.user) | Q(pk=self.user.pk),
            ).order_by('username')
        self.fields['under_supervision'].required = False

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def clean_user_type(self):
        user_type = self.cleaned_data['user_type']
        if user_type not in ('manager', 'employee'):
            raise forms.ValidationError('Managers can only create Manager or Employee accounts.')
        return user_type

    def clean_under_supervision(self):
        supervisor = self.cleaned_data.get('under_supervision')
        if supervisor and self.user:
            if supervisor.pk != self.user.pk and supervisor.created_by_id != self.user.id:
                raise forms.ValidationError(
                    'Selected supervisor must be yourself or a manager you created.',
                )
        return supervisor

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.designation = self.cleaned_data.get('designation', '')
        user.user_type = self.cleaned_data['user_type']
        if user.user_type == 'employee':
            user.under_supervision = self.cleaned_data.get('under_supervision')
        else:
            user.under_supervision = None
        if self.user:
            user.created_by = self.user
            if self.user.company_id:
                user.company_id = self.user.company_id
        if commit:
            user.save()
        return user


class ManagerUserEditForm(forms.ModelForm):
    """Edit manager/employee accounts — managers cannot change users to admin."""
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'user_type', 'first_name', 'last_name', 'designation', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'user_type': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].choices = MANAGER_USER_TYPE_CHOICES

    def clean_user_type(self):
        user_type = self.cleaned_data['user_type']
        if user_type not in ('manager', 'employee'):
            raise forms.ValidationError('Managers can only assign Manager or Employee type.')
        return user_type

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = CustomUser.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email


class UserProfileEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'designation', 'contact_number', 'avatar']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }


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
    package_count = forms.IntegerField(
        label='Number of Package', min_value=1, initial=1,
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
    manager_username = forms.CharField(
        label='Username', max_length=150,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    client_email = forms.EmailField(
        label='E-mail (Client)',
        widget=forms.EmailInput(attrs=FORM_CONTROL),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End Date must be on or after Start Date.')
        username = (cleaned.get('manager_username') or '').strip()
        if username and CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError({
                'manager_username': f'Username "{username}" is already taken.',
            })
        email = (cleaned.get('client_email') or '').strip()
        if email and CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError({
                'client_email': 'A user with this email already exists.',
            })
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

        username = (cleaned.get('manager_username') or '').strip()
        if username:
            qs = CustomUser.objects.filter(username=username)
            if self.company and self.company.authorized_manager_id:
                qs = qs.exclude(pk=self.company.authorized_manager_id)
            if qs.exists():
                raise forms.ValidationError({
                    'manager_username': f'Username "{username}" is already taken.',
                })

        email = (cleaned.get('client_email') or '').strip()
        if email:
            qs = CustomUser.objects.filter(email__iexact=email)
            if self.company and self.company.authorized_manager_id:
                qs = qs.exclude(pk=self.company.authorized_manager_id)
            if qs.exists():
                raise forms.ValidationError({
                    'client_email': 'A user with this email already exists.',
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
        'client_email': company.client_email or (mgr.email if mgr else ''),
        'manager_username': mgr.username if mgr else '',
        'project_manager_name': pm_name,
    }
    if authorization:
        initial.update({
            'start_date': authorization.start_date,
            'end_date': authorization.end_date,
            'package_count': authorization.package_count,
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
        fields = ['title', 'category', 'file', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
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
        fields = ['package_instance', 'company_name', 'factory_name', 'location',
                  'factory_address', 'contact_person', 'contact_email', 'contact_mobile',
                  'report_type', 'year', 'project_number']
        widgets = {
            'package_instance': forms.Select(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'factory_name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'factory_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'report_type': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'project_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ['name', 'email', 'role']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }


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
    """Generic form record - data stored as JSON via hidden field or dynamic fields."""
    form_data_json = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = FormRecord
        fields = ['created_by_name']
        widgets = {
            'created_by_name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CVApprovalForm(forms.ModelForm):
    class Meta:
        model = EmployeeRecord
        fields = ['cv_approval_status']
        widgets = {
            'cv_approval_status': forms.Select(attrs={'class': 'form-control'}),
        }


class ViewPackageSearchForm(forms.Form):
    vvb_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name of VVB'})
    )
