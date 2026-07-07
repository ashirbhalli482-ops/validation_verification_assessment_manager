from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.templatetags.static import static
from django.utils import timezone
import os
import secrets


USER_TYPE_CHOICES = [
    ('admin', 'Admin'),
    ('manager', 'Manager'),
    ('employee', 'Employee'),
]

LIBRARY_CATEGORY_CHOICES = [
    ('standards', 'Standards Info'),
    ('procedure', 'Procedure'),
    ('regulation', 'Regulation Info'),
    ('general', 'General Info'),
]

FORM_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted for Review'),
    ('returned', 'Returned for Editing'),
    ('approved', 'Approved'),
    ('finalized', 'Finalized'),
]

TEAM_ROLE_CHOICES = [
    ('team_member', 'Team Member (Level 3)'),
    ('senior_reviewer', 'Senior Reviewer (Level 2)'),
    ('project_manager', 'Project Manager'),
]

CV_APPROVAL_CHOICES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('not_approved', 'Not Approved'),
    ('in_training', 'In Training'),
]

PROJECT_PHASE_CHOICES = [
    ('pre_engagement', 'Pre-engagement'),
    ('execution', 'Execution'),
    ('review', 'Review'),
]

PROJECT_DOCUMENT_TYPE_CHOICES = [
    ('internal', 'Internal'),
    ('external', 'External'),
]

USER_ROLE_CHOICES = [
    ('verifier_1', 'Verifier 1'),
    ('verifier_2', 'Verifier 2'),
    ('verifier_3', 'Verifier 3'),
    ('lead_verifier', 'Lead Verifier'),
    ('co_lead_verifier', 'Co-Lead Verifier'),
    ('technical_expert_1', 'Technical Expert 1'),
    ('technical_expert_2', 'Technical Expert 2'),
    ('peer_reviewer', 'Peer Reviewer'),
]


class CustomUser(AbstractUser):
    """Admin, Manager (VVB/Project Manager), or Employee."""
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=15, choices=USER_TYPE_CHOICES)
    user_role = models.CharField(
        max_length=30, choices=USER_ROLE_CHOICES, blank=True, verbose_name='User Role',
    )
    designation = models.CharField(max_length=100, blank=True, null=True)
    position_title = models.CharField(max_length=150, blank=True, verbose_name='Position Title')
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    cv = models.FileField(upload_to='core/cvs/', blank=True, null=True)
    company = models.ForeignKey(
        'Company', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managers'
    )
    created_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_users'
    )
    created_date = models.DateField(auto_now_add=True)
    created_time = models.TimeField(auto_now_add=True)
    under_supervision = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='supervised_users'
    )
    avatar = models.ImageField(upload_to='core/avatar', blank=True)

    def __str__(self):
        return self.get_full_name() or self.username

    def get_subordinates(self):
        return CustomUser.objects.filter(under_supervision=self)

    def can_manage_user(self, target_user):
        if self.user_type == 'admin':
            return True
        if self.user_type == 'manager':
            if target_user.user_type == 'admin':
                return False
            if target_user == self:
                return True
            if target_user.created_by_id == self.id:
                return target_user.user_type in ('manager', 'employee')
            if target_user.under_supervision_id == self.id:
                return target_user.user_type == 'employee'
            return TeamMember.objects.filter(
                project__manager=self, user=target_user, is_active=True
            ).exists()
        return False

    def save(self, *args, **kwargs):
        if not self.pk:
            self.is_active = True
        super().save(*args, **kwargs)

    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            avatar_path = self.avatar.path if hasattr(self.avatar, 'path') else None
            if avatar_path and os.path.isfile(avatar_path):
                return self.avatar.url
        return static('core/img/avatar/blank_profile.png')


class Company(models.Model):
    """Company with authorized VVB / Project Manager credentials."""
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    abbreviation = models.CharField(max_length=20, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    version = models.CharField(max_length=50, blank=True)
    designated_person = models.CharField(max_length=200, blank=True)
    client_email = models.EmailField(blank=True)
    project_limit = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Maximum number of projects the authorized manager can create',
    )
    authorized_manager = models.OneToOneField(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_company', limit_choices_to={'user_type': 'manager'}
    )
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_companies'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self):
        return self.name

    def manager_project_count(self):
        if not self.authorized_manager_id:
            return 0
        return Project.objects.filter(manager_id=self.authorized_manager_id).count()

    def projects_remaining(self):
        return max(0, self.project_limit - self.manager_project_count())


class PackageTemplate(models.Model):
    """Master package definition (e.g. Validation Package Set)."""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SubPackage(models.Model):
    """Sub-package sections: P1-A, P1-B, P1-C, P1-D."""
    package_template = models.ForeignKey(
        PackageTemplate, on_delete=models.CASCADE, related_name='sub_packages'
    )
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'code']
        unique_together = ['package_template', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


FORM_TYPE_CHOICES = [
    ('project', 'Project'),
    ('master_record', 'Master Record'),
    ('proposal', 'Proposal'),
    ('others', 'Others'),
]

FORM_TYPE_TO_CATEGORY = {
    'project': 'limited_form',
    'master_record': 'master_record',
    'proposal': 'unlimited_use',
    'others': 'limited_form',
}


class FormDefinition(models.Model):
    """Form detail definition (form number, name, type) within a sub-package."""
    FORM_CATEGORY_CHOICES = [
        ('master_record', 'Master Record'),
        ('unlimited_use', 'Unlimited Use'),
        ('limited_form', 'Limited Use Form'),
        ('report', 'Report'),
    ]
    sub_package = models.ForeignKey(
        SubPackage, on_delete=models.CASCADE, related_name='forms'
    )
    code = models.CharField(max_length=20, verbose_name='Form Number')
    name = models.CharField(max_length=200, verbose_name='Form Name')
    description = models.TextField(blank=True)
    form_type = models.CharField(
        max_length=20, choices=FORM_TYPE_CHOICES, default='project',
        verbose_name='Form Type',
    )
    category = models.CharField(
        max_length=20, choices=FORM_CATEGORY_CHOICES, default='limited_form',
    )
    is_public = models.BooleanField(
        default=False,
        help_text='Public forms (e.g. F-02-IRR) accessible without login'
    )
    order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_form_definitions',
        help_text='Set when an admin creates this form via Form Details.',
    )

    class Meta:
        verbose_name = 'Form Detail'
        verbose_name_plural = 'Form Details'
        ordering = ['order', 'code']
        unique_together = ['sub_package', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class PackageAuthorization(models.Model):
    """Admin authorizes packages to a VVB / Project Manager."""
    package_template = models.ForeignKey(
        PackageTemplate, on_delete=models.CASCADE, related_name='authorizations'
    )
    manager = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='package_authorizations',
        limit_choices_to={'user_type': 'manager'}
    )
    vvb_name = models.CharField(max_length=200, verbose_name='Name of VVB')
    abbreviation = models.CharField(max_length=20)
    year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    package_count = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Number of package sets (e.g. 1, 10, 100)'
    )
    access_password = models.CharField(
        max_length=128, blank=True,
        help_text='Single password for all projects/packages under this VVB authorization'
    )
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_authorizations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.vvb_name} - {self.package_count} packages ({self.year})'

    def save(self, *args, **kwargs):
        if not self.access_password:
            self.access_password = secrets.token_urlsafe(8)
        super().save(*args, **kwargs)

    def generate_package_instances(self):
        """Generate P1..Pn package instances and sync authorized forms/library."""
        for form_def in FormDefinition.objects.filter(
            sub_package__package_template=self.package_template,
            created_by__isnull=False,
        ):
            AuthorizedForm.objects.get_or_create(
                authorization=self,
                form_definition=form_def,
                defaults={'is_active': False},
            )
        for doc in LibraryDocument.objects.all():
            AuthorizedLibraryDocument.objects.get_or_create(
                authorization=self,
                library_document=doc,
                defaults={'is_active': True},
            )

        existing = self.instances.count()
        for i in range(existing + 1, self.package_count + 1):
            PackageInstance.objects.create(
                authorization=self,
                package_number=i,
                code=f'P{i}',
                name=f'P{i}-{self.abbreviation}-{self.year}',
            )

        for inst in self.instances.filter(package_number__gt=self.package_count):
            if not inst.projects.exists():
                inst.delete()


class PackageInstance(models.Model):
    """Generated package instance: P1, P2, ... P20."""
    authorization = models.ForeignKey(
        PackageAuthorization, on_delete=models.CASCADE, related_name='instances'
    )
    package_number = models.PositiveIntegerField()
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['package_number']
        unique_together = ['authorization', 'package_number']

    def __str__(self):
        return self.name


class AuthorizedForm(models.Model):
    """Toggle forms active/inactive per authorization."""
    authorization = models.ForeignKey(
        PackageAuthorization, on_delete=models.CASCADE, related_name='authorized_forms'
    )
    form_definition = models.ForeignKey(
        FormDefinition, on_delete=models.CASCADE, related_name='authorizations'
    )
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ['authorization', 'form_definition']

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f'{self.form_definition.code} ({status})'


class AuthorizedLibraryDocument(models.Model):
    """Library documents authorized per VVB package authorization."""
    authorization = models.ForeignKey(
        PackageAuthorization, on_delete=models.CASCADE, related_name='authorized_library'
    )
    library_document = models.ForeignKey(
        'LibraryDocument', on_delete=models.CASCADE, related_name='authorizations'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['authorization', 'library_document']

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f'{self.library_document.title} ({status})'


class LibraryDocument(models.Model):
    """Main library documents uploaded by admin (view-only for users)."""
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=LIBRARY_CATEGORY_CHOICES)
    file = models.FileField(upload_to='core/library/')
    description = models.TextField(blank=True)
    allowed_companies = models.ManyToManyField(
        'Company', blank=True, related_name='library_documents',
        help_text='Client companies that may view this document in the library',
    )
    uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'title']

    def __str__(self):
        return f'{self.title} ({self.get_category_display()})'


class DropdownList(models.Model):
    """Configurable drop-down lists feeding form fields."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DropdownOption(models.Model):
    dropdown_list = models.ForeignKey(
        DropdownList, on_delete=models.CASCADE, related_name='options'
    )
    value = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'value']

    def __str__(self):
        return self.value


class Project(models.Model):
    """Manager-created project allocated to one package instance."""
    package_instance = models.ForeignKey(
        PackageInstance, on_delete=models.CASCADE, related_name='projects'
    )
    manager = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='managed_projects',
        limit_choices_to={'user_type': 'manager'}
    )
    company_name = models.CharField(max_length=200)
    factory_name = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    factory_address = models.TextField(blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_mobile = models.CharField(max_length=20, blank=True)
    report_type = models.CharField(max_length=100, blank=True)
    engagement_year = models.CharField(max_length=100, blank=True)
    phase = models.CharField(max_length=20, choices=PROJECT_PHASE_CHOICES, blank=True)
    document_type = models.CharField(max_length=20, choices=PROJECT_DOCUMENT_TYPE_CHOICES, blank=True)
    year = models.PositiveIntegerField()
    project_number = models.CharField(max_length=50, unique=True)
    access_password = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project_number} - {self.company_name}'

    def save(self, *args, **kwargs):
        if self.package_instance_id:
            auth = self.package_instance.authorization
            if not self.access_password:
                self.access_password = auth.access_password
        elif not self.access_password:
            self.access_password = secrets.token_urlsafe(8)
        super().save(*args, **kwargs)

    @property
    def vvb_password(self):
        return self.package_instance.authorization.access_password


class TeamMember(models.Model):
    """Team authorization for a project (email + shared password access)."""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='team_members'
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=TEAM_ROLE_CHOICES)
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='team_assignments'
    )
    is_active = models.BooleanField(default=True)
    authorized_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['project', 'email']

    def __str__(self):
        return f'{self.name} ({self.get_role_display()}) - {self.project}'


class EmployeeRecord(models.Model):
    """Master employee records managed by Project Manager."""
    manager = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='employee_records',
        limit_choices_to={'user_type': 'manager'}
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employee_record'
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20, blank=True)
    position = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=50, blank=True)
    cv = models.FileField(upload_to='core/employee_cvs/', blank=True, null=True)
    cv_approval_status = models.CharField(
        max_length=20, choices=CV_APPROVAL_CHOICES, default='pending'
    )
    cv_approved_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_cvs'
    )
    cv_approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FormRecord(models.Model):
    """Individual form record with workflow and JSON data storage."""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='form_records'
    )
    form_definition = models.ForeignKey(
        FormDefinition, on_delete=models.CASCADE, related_name='records'
    )
    created_by_name = models.CharField(max_length=100)
    created_by_user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_form_records'
    )
    created_date = models.DateField(auto_now_add=True)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=FORM_STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    finalized_by_name = models.CharField(max_length=100, blank=True)
    finalized_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finalized_forms'
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.form_definition.code} - {self.project.project_number}'

    def _team_member(self, user):
        from .access import get_team_member
        return get_team_member(user, self.project)

    def can_edit(self, user):
        if user.user_type == 'admin':
            return True
        if self.status in ('approved', 'finalized', 'submitted'):
            return False
        if user.user_type == 'manager' and self.project.manager == user:
            return True
        tm = self._team_member(user)
        if tm and tm.role == 'team_member':
            return self.created_by_user == user and self.status in ('draft', 'returned')
        return False

    def can_submit(self, user):
        if self.status not in ('draft', 'returned'):
            return False
        if user.user_type == 'manager' and self.project.manager == user:
            return True
        tm = self._team_member(user)
        return (
            tm is not None
            and tm.role == 'team_member'
            and self.created_by_user == user
        )

    def can_review(self, user):
        if self.status not in ('submitted', 'approved'):
            return False
        if self.status == 'finalized':
            return False
        if self.project.manager == user:
            return False
        if self.reviews.filter(reviewer=user).exists():
            return False
        if self.reviews.filter(approved=True).count() >= 3:
            return False
        return TeamMember.objects.filter(
            project=self.project, user=user, role='senior_reviewer', is_active=True
        ).exists()

    def can_finalize(self, user):
        return (
            user.user_type == 'manager'
            and self.project.manager == user
            and self.status == 'approved'
            and self.reviews.filter(approved=True).exists()
        )

    def has_user_reviewed(self, user):
        return self.reviews.filter(reviewer=user, approved=True).exists()

    def senior_reviews_complete(self):
        """At least one senior approval is required before PM finalization."""
        return self.reviews.filter(approved=True).exists()


class FormReview(models.Model):
    """Up to three senior-level reviews per form."""
    form_record = models.ForeignKey(
        FormRecord, on_delete=models.CASCADE, related_name='reviews'
    )
    reviewer = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    reviewer_name = models.CharField(max_length=100)
    reviewer_role = models.CharField(max_length=100)
    review_order = models.PositiveIntegerField(default=1)
    approved = models.BooleanField(default=False)
    returned = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['review_order']
        unique_together = ['form_record', 'review_order']

    def __str__(self):
        return f'Review {self.review_order} by {self.reviewer_name}'


class Notification(models.Model):
    recipient = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='notifications'
    )
    sender = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_notifications'
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'To: {self.recipient.get_full_name()} | {self.message[:40]}...'


def notify_user(recipient, message, sender=None, link=''):
    """Helper to create notifications."""
    if recipient:
        Notification.objects.create(
            recipient=recipient, sender=sender, message=message, link=link
        )
