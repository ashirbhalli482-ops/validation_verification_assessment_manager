from django.db import migrations, models


def forwards_normalize_summaries(apps, schema_editor):
    FormTableLayout = apps.get_model('core', 'FormTableLayout')
    for layout in FormTableLayout.objects.all().iterator():
        raw = layout.table_summary
        if isinstance(raw, list):
            continue
        if isinstance(raw, dict) and (raw.get('enabled') or raw.get('columns') or raw.get('rows')):
            layout.table_summary = [raw]
            layout.save(update_fields=['table_summary'])
        elif not raw:
            layout.table_summary = []
            layout.save(update_fields=['table_summary'])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_formrecord_standalone_owner_manager'),
    ]

    operations = [
        migrations.AlterField(
            model_name='formtablelayout',
            name='table_summary',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'One or more table summaries (list). Each item: {enabled, title, '
                    'columns:[{label, subheader}], rows:[{label, cells:[{value, formula}]}], '
                    'dropdowns:[{col, rows, options, is_active, depends_on_table_col?, '
                    'depends_on_col?, option_map?}]}. '
                    'Legacy single-dict format is still accepted on read. '
                    'Admin formulas e.g. =COUNTIF("Bases Risk Rating","High"), '
                    '=COUNTIFS(B:B,"Inherent Risk",F:F,"High"), or '
                    '=((B2*3)+(C2*2)+(D2*1))/(B2+C2+D2).'
                ),
            ),
        ),
        migrations.RunPython(forwards_normalize_summaries, backwards_noop),
    ]
