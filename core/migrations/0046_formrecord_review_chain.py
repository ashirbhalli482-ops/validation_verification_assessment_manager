from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_formrecord_review_assignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='formrecord',
            name='review_chain',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Ordered user IDs in the senior-review path; reject pops one step back.',
            ),
        ),
    ]
