from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_authorized_library_and_employee_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='client_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='company',
            name='designated_person',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='company',
            name='issue_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='version',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='formdefinition',
            name='category',
            field=models.CharField(
                choices=[
                    ('master_record', 'Master Record'),
                    ('unlimited_use', 'Unlimited Use'),
                    ('limited_form', 'Limited Use Form'),
                    ('report', 'Report'),
                ],
                default='limited_form',
                max_length=20,
            ),
        ),
    ]
