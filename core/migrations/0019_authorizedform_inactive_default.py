from django.db import migrations, models


def deactivate_all_authorized_forms(apps, schema_editor):
    AuthorizedForm = apps.get_model('core', 'AuthorizedForm')
    AuthorizedForm.objects.update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_company_project_limit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='authorizedform',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(deactivate_all_authorized_forms, migrations.RunPython.noop),
    ]
