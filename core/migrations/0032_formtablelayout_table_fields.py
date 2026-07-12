from django.core.validators import MinValueValidator
from django.db import migrations, models


def normalize_column_headers(apps, schema_editor):
    FormTableLayout = apps.get_model('core', 'FormTableLayout')
    for layout in FormTableLayout.objects.all():
        normalized = []
        for entry in layout.column_headers or []:
            if isinstance(entry, dict):
                label = (entry.get('label') or '').strip() or 'Column'
                normalized.append({
                    'label': label,
                    'is_active': bool(entry.get('is_active', True)),
                })
            elif isinstance(entry, str):
                label = entry.strip() or 'Column'
                normalized.append({'label': label, 'is_active': True})
        layout.column_headers = normalized
        layout.save(update_fields=['column_headers'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_project_client_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='formtablelayout',
            name='table_number',
            field=models.PositiveIntegerField(
                default=1,
                validators=[MinValueValidator(1)],
                verbose_name='Number of Table',
            ),
        ),
        migrations.AddField(
            model_name='formtablelayout',
            name='table_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='Name of Table'),
        ),
        migrations.AddField(
            model_name='formtablelayout',
            name='notes',
            field=models.TextField(blank=True, verbose_name='Table Notes'),
        ),
        migrations.AlterField(
            model_name='formtablelayout',
            name='row_count',
            field=models.PositiveIntegerField(
                default=100,
                validators=[MinValueValidator(1)],
            ),
        ),
        migrations.AlterField(
            model_name='formtablelayout',
            name='column_headers',
            field=models.JSONField(
                default=list,
                help_text='Ordered list of column objects: {label, is_active}.',
            ),
        ),
        migrations.RunPython(normalize_column_headers, migrations.RunPython.noop),
    ]
