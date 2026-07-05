from django.core.validators import MinValueValidator
from django.db import migrations, models


def copy_project_limit_from_authorization(apps, schema_editor):
    Company = apps.get_model('core', 'Company')
    PackageAuthorization = apps.get_model('core', 'PackageAuthorization')
    for company in Company.objects.filter(authorized_manager_id__isnull=False):
        auth = PackageAuthorization.objects.filter(
            manager_id=company.authorized_manager_id,
        ).order_by('-created_at').first()
        if auth:
            company.project_limit = auth.package_count
            company.save(update_fields=['project_limit'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_company_package_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='project_limit',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Maximum number of projects the authorized manager can create',
                validators=[MinValueValidator(1)],
            ),
        ),
        migrations.RunPython(copy_project_limit_from_authorization, migrations.RunPython.noop),
    ]
