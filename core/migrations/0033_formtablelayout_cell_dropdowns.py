from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_formtablelayout_table_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='formtablelayout',
            name='cell_dropdowns',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Cell dropdown configs: {row, col, options, is_active}.',
            ),
        ),
    ]
