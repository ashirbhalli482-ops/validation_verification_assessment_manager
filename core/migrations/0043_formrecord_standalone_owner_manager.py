# Generated manually for standalone manager FormRecords

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0042_formtablelayout_table_summary'),
    ]

    operations = [
        migrations.AddField(
            model_name='formrecord',
            name='owner_manager',
            field=models.ForeignKey(
                blank=True,
                help_text='Set for manager standalone forms not linked to a project.',
                limit_choices_to={'user_type': 'manager'},
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='owned_standalone_form_records',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='formrecord',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='form_records',
                to='core.project',
            ),
        ),
        migrations.AddConstraint(
            model_name='formrecord',
            constraint=models.UniqueConstraint(
                condition=models.Q(('owner_manager__isnull', False), ('project__isnull', True)),
                fields=('owner_manager', 'form_definition'),
                name='uniq_standalone_manager_form',
            ),
        ),
    ]
