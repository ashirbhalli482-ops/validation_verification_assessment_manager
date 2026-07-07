"""Default package template and sub-packages (no hardcoded forms)."""

from core.models import PackageTemplate, SubPackage

DEFAULT_TEMPLATE_NAME = 'Validation Verification Package'

ORDER_MAP = {'P1-A': 1, 'P1-B': 2, 'P1-C': 3, 'P1-D': 4}


def _ensure_sub_packages(template):
    """Create empty sub-package sections for admin-created forms."""
    for code, order in ORDER_MAP.items():
        SubPackage.objects.get_or_create(
            package_template=template,
            code=code,
            defaults={'name': code, 'order': order},
        )


def ensure_default_package_seed():
    """Idempotently ensure an active package template and sub-packages exist."""
    template = PackageTemplate.objects.filter(is_active=True).first()
    if not template:
        template, _ = PackageTemplate.objects.get_or_create(
            name=DEFAULT_TEMPLATE_NAME,
            defaults={
                'description': 'Default VVB assessment package set',
                'is_active': True,
            },
        )
        if not template.is_active:
            template.is_active = True
            template.save(update_fields=['is_active'])
    _ensure_sub_packages(template)
    return template


def get_active_package_template():
    """Return the active package template, auto-creating structure when missing."""
    return ensure_default_package_seed()
