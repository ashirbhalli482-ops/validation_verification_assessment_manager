from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_column_dropdowns_only'),
    ]

    operations = [
        migrations.AlterField(
            model_name='formtablelayout',
            name='form_definition',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='table_layouts',
                to='core.formdefinition',
            ),
        ),
        migrations.AddConstraint(
            model_name='formtablelayout',
            constraint=models.UniqueConstraint(
                fields=('form_definition', 'table_number'),
                name='unique_table_number_per_form',
            ),
        ),
    ]
