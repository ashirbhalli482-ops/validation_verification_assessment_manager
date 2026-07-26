from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_formtablelayout_dependent_dropdowns_help'),
    ]

    operations = [
        migrations.AddField(
            model_name='formtablelayout',
            name='table_summary',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'Optional table summary: {enabled, title, columns:[{label}], '
                    'rows:[{label, cells:[{value, formula}]}]}. Formulas are optional text '
                    '(e.g. =SUM(C0) to sum main-table column 0).'
                ),
            ),
        ),
    ]
