from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_project_engagement_phase_document'),
    ]

    operations = [
        migrations.AddField(
            model_name='librarydocument',
            name='allowed_companies',
            field=models.ManyToManyField(
                blank=True,
                help_text='Client companies that may view this document in the library',
                related_name='library_documents',
                to='core.company',
            ),
        ),
    ]
