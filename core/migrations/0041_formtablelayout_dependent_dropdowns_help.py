from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_formtablelayout_dropdown_rows_help'),
    ]

    operations = [
        migrations.AlterField(
            model_name='formtablelayout',
            name='cell_dropdowns',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'Dropdown configs: {col, rows, options, is_active, depends_on_col?, option_map?}. '
                    'Empty rows = all rows. When depends_on_col is set, option_map maps parent value → child options.'
                ),
            ),
        ),
    ]
