from django.db import migrations, models


def set_form_type_from_category(apps, schema_editor):
    FormDefinition = apps.get_model('core', 'FormDefinition')
    mapping = {
        'master_record': 'master_record',
        'unlimited_use': 'proposal',
        'limited_form': 'project',
        'report': 'proposal',
    }
    for form_def in FormDefinition.objects.all():
        form_def.form_type = mapping.get(form_def.category, 'project')
        form_def.save(update_fields=['form_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_librarydocument_allowed_companies'),
    ]

    operations = [
        migrations.AddField(
            model_name='formdefinition',
            name='form_type',
            field=models.CharField(
                choices=[
                    ('project', 'Project'),
                    ('master_record', 'Master Record'),
                    ('proposal', 'Proposal'),
                ],
                default='project',
                max_length=20,
            ),
        ),
        migrations.RunPython(set_form_type_from_category, migrations.RunPython.noop),
    ]
