from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def remove_seeded_forms(apps, schema_editor):
    """Remove hardcoded seed forms; keep only admin-created forms going forward."""
    FormDefinition = apps.get_model('core', 'FormDefinition')
    FormDefinition.objects.filter(created_by__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_customuser_user_role_position_title'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='formdefinition',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Set when an admin creates this form via Form Details.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_form_definitions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(remove_seeded_forms, migrations.RunPython.noop),
    ]
