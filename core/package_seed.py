"""Default package template, sub-packages, and form definitions (idempotent)."""

from core.models import PackageTemplate, SubPackage, FormDefinition

DEFAULT_TEMPLATE_NAME = 'Validation Verification Package'

# Form codes grouped by sub-package with category for the package selection grid.
DEFAULT_FORMS = {
    'P1-A': [
        ('F-01A-MRT', 'Master Record Template', 'master_record'),
        ('F-01B-MRP', 'Master Record Package', 'master_record'),
        ('F-01C-MRC', 'Master Record Competency', 'master_record'),
        ('F-01D-PPS', 'Project Package Summary', 'master_record'),
    ],
    'P1-B': [
        ('F-02-IIR', 'Customer Inquiry', 'unlimited_use'),
        ('F-03-PEB', 'Project Evaluation Board', 'unlimited_use'),
        ('F-04A-CIO', 'Customer Inquiry Out', 'unlimited_use'),
        ('F-04B-CIT', 'Customer Inquiry Tracking', 'unlimited_use'),
        ('F-05-PTM', 'Project Time Management', 'unlimited_use'),
        ('F-06-PSP', 'Project Summary Package', 'unlimited_use'),
    ],
    'P1-C': [
        ('F-07-FBA', 'Form B Assessment', 'limited_form'),
        ('F-08A-CCS', 'CCS Form A', 'limited_form'),
        ('F-08B-CCS', 'CCS Form B', 'limited_form'),
        ('F-09-PRA', 'Project Risk Assessment', 'limited_form'),
        ('F-10-EGP', 'Environmental Gap', 'limited_form'),
        ('F-11-PVP', 'Project Validation Plan', 'limited_form'),
        ('F-12-SVP', 'Site Validation Plan', 'limited_form'),
        ('F-13-QMA', 'Quality Management Audit', 'limited_form'),
        ('F-14-PCM', 'Project Change Management', 'limited_form'),
        ('F-15-OIL', 'Operational Impact Log', 'limited_form'),
        ('F-16-IRR', 'Issue Resolution Report', 'limited_form'),
        ('F-17-PCS', 'Project Closure Summary', 'limited_form'),
    ],
    'P1-D': [
        ('R-01-FFS', 'Final Findings Summary', 'report'),
        ('R-02A-VRT', 'Validation Report A', 'report'),
        ('R-02B-VRT', 'Validation Report B', 'report'),
        ('I-01-ISO', 'ISO Information', 'report'),
        ('I-02-P&R', 'Procedures & Regulations', 'report'),
        ('I-03-Tabl', 'Reference Tables', 'report'),
    ],
}

CATEGORY_TO_FORM_TYPE = {
    'master_record': 'master_record',
    'unlimited_use': 'proposal',
    'limited_form': 'project',
    'report': 'proposal',
}

ORDER_MAP = {'P1-A': 1, 'P1-B': 2, 'P1-C': 3, 'P1-D': 4}


def _seed_sub_packages_and_forms(template):
    for code, forms in DEFAULT_FORMS.items():
        sub, _ = SubPackage.objects.get_or_create(
            package_template=template,
            code=code,
            defaults={'name': code, 'order': ORDER_MAP[code]},
        )
        for idx, (form_code, form_name, category) in enumerate(forms):
            FormDefinition.objects.update_or_create(
                sub_package=sub,
                code=form_code,
                defaults={
                    'name': form_name,
                    'order': idx,
                    'category': category,
                    'form_type': CATEGORY_TO_FORM_TYPE.get(category, 'project'),
                    'is_public': form_code in ('F-02-IIR', 'F-02-IRR'),
                },
            )


def ensure_default_package_seed():
    """Idempotently ensure an active package template, sub-packages, and default forms exist."""
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
    _seed_sub_packages_and_forms(template)
    return template


def get_active_package_template():
    """Return the active package template, auto-creating default data when missing."""
    return ensure_default_package_seed()
