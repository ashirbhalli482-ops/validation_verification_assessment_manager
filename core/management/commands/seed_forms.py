from django.core.management.base import BaseCommand
from core.models import PackageTemplate, SubPackage, FormDefinition


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


class Command(BaseCommand):
    help = 'Seed default package template with sub-packages P1-A through P1-D and forms'

    def handle(self, *args, **options):
        template, _ = PackageTemplate.objects.get_or_create(
            name='Validation Verification Package',
            defaults={'description': 'Default VVB assessment package set', 'is_active': True},
        )
        order_map = {'P1-A': 1, 'P1-B': 2, 'P1-C': 3, 'P1-D': 4}
        for code, forms in DEFAULT_FORMS.items():
            sub, _ = SubPackage.objects.get_or_create(
                package_template=template,
                code=code,
                defaults={'name': code, 'order': order_map[code]},
            )
            for idx, (form_code, form_name, category) in enumerate(forms):
                FormDefinition.objects.update_or_create(
                    sub_package=sub,
                    code=form_code,
                    defaults={
                        'name': form_name,
                        'order': idx,
                        'category': category,
                        'is_public': form_code in ('F-02-IIR', 'F-02-IRR'),
                    },
                )
        self.stdout.write(self.style.SUCCESS('Seeded package template, sub-packages, and forms.'))
