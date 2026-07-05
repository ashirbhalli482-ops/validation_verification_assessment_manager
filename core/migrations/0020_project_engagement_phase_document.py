from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_authorizedform_inactive_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='document_type',
            field=models.CharField(
                blank=True,
                choices=[('internal', 'Internal'), ('external', 'External')],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='engagement_year',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='project',
            name='phase',
            field=models.CharField(
                blank=True,
                choices=[
                    ('pre_engagement', 'Pre-engagement'),
                    ('execution', 'Execution'),
                    ('review', 'Review'),
                ],
                max_length=20,
            ),
        ),
    ]
