from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_formtablelayout_cell_dropdowns'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'read', '-created_at'], name='core_notif_recip_read_idx'),
        ),
    ]
