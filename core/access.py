"""Centralized access control for employees and project resources."""

from .models import TeamMember, AuthorizedForm, AuthorizedLibraryDocument


def get_team_member(user, project):
    if not user.is_authenticated:
        return None
    return TeamMember.objects.filter(
        project=project, user=user, is_active=True
    ).first()


def get_employee_projects(user):
    if not user.is_authenticated or user.user_type != 'employee':
        return []
    return list(
        user.team_assignments.filter(is_active=True)
        .select_related('project', 'project__package_instance', 'project__package_instance__authorization')
        .order_by('-project__created_at')
    )


def can_access_project(user, project, session=None):
    if not user.is_authenticated:
        return False
    if user.user_type == 'admin':
        return True
    if user.user_type == 'manager' and project.manager_id == user.id:
        return True
    tm = get_team_member(user, project)
    if tm:
        return True
    if session:
        email = session.get(f'project_access_{project.pk}')
        if email and TeamMember.objects.filter(
            project=project, email__iexact=email, is_active=True
        ).exists():
            return True
    return False


def can_employee_login_only(user):
    """Employees may only use login, projects, forms, library, reports, notifications."""
    return user.is_authenticated and user.user_type == 'employee'


def is_form_authorized_for_project(form_definition, project):
    auth = project.package_instance.authorization
    return AuthorizedForm.objects.filter(
        authorization=auth,
        form_definition=form_definition,
        is_active=True,
    ).exists()


def can_access_form(user, project, form_definition):
    if not can_access_project(user, project):
        return False
    if not is_form_authorized_for_project(form_definition, project):
        return False
    if user.user_type == 'admin':
        return True
    if user.user_type == 'manager' and project.manager_id == user.id:
        return True
    return get_team_member(user, project) is not None


def can_create_form_record(user, project, form_definition):
    if not can_access_form(user, project, form_definition):
        return False
    if user.user_type in ('admin', 'manager'):
        return True
    tm = get_team_member(user, project)
    return tm is not None and tm.role == 'team_member'


def can_access_library_document(user, document):
    if user.user_type == 'admin':
        return True
    if user.user_type == 'manager':
        auth_ids = user.package_authorizations.values_list('id', flat=True)
        return AuthorizedLibraryDocument.objects.filter(
            authorization_id__in=auth_ids,
            library_document=document,
            is_active=True,
        ).exists()
    if user.user_type != 'employee':
        return False
    auth_ids = user.team_assignments.filter(is_active=True).values_list(
        'project__package_instance__authorization_id', flat=True
    )
    return AuthorizedLibraryDocument.objects.filter(
        authorization_id__in=auth_ids,
        library_document=document,
        is_active=True,
    ).exists()


def get_authorized_library_documents(user):
    from .models import LibraryDocument

    if user.user_type == 'admin':
        return LibraryDocument.objects.all()
    if user.user_type == 'manager':
        auth_ids = user.package_authorizations.values_list('id', flat=True)
    elif user.user_type == 'employee':
        auth_ids = user.team_assignments.filter(is_active=True).values_list(
            'project__package_instance__authorization_id', flat=True
        )
    else:
        return LibraryDocument.objects.none()
    doc_ids = AuthorizedLibraryDocument.objects.filter(
        authorization_id__in=auth_ids, is_active=True
    ).values_list('library_document_id', flat=True)
    return LibraryDocument.objects.filter(id__in=doc_ids)


def is_report_form(form_definition):
    code = (form_definition.code or '').upper()
    name = (form_definition.name or '').upper()
    return 'LIB' in code or 'REPORT' in code or 'REPORT' in name


def can_view_report(user, record):
    if not is_report_form(record.form_definition):
        return False
    if record.status not in ('approved', 'finalized'):
        return False
    return can_access_form(user, record.project, record.form_definition)


def get_manager_manageable_users(manager):
    """Users a manager may view/edit/delete (manager or employee only)."""
    from django.db.models import Q
    from .models import CustomUser

    team_user_ids = TeamMember.objects.filter(
        project__manager=manager, is_active=True, user__isnull=False
    ).values_list('user_id', flat=True)
    return CustomUser.objects.filter(
        user_type__in=['manager', 'employee'],
    ).filter(
        Q(created_by=manager) | Q(under_supervision=manager) | Q(id__in=team_user_ids)
    ).distinct()
