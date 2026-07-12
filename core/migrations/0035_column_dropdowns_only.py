from django.db import migrations


def column_dropdowns_only(apps, schema_editor):
    FormTableLayout = apps.get_model('core', 'FormTableLayout')
    for layout in FormTableLayout.objects.all():
        normalized = []
        seen = set()
        for entry in layout.cell_dropdowns or []:
            if not isinstance(entry, dict):
                continue
            try:
                col = int(entry.get('col', 0))
            except (TypeError, ValueError):
                continue
            options = [
                str(option).strip()
                for option in entry.get('options', [])
                if str(option).strip()
            ]
            if not options or col in seen:
                continue
            seen.add(col)
            normalized.append({
                'col': col,
                'options': options,
                'is_active': bool(entry.get('is_active', True)),
            })
        layout.cell_dropdowns = normalized
        layout.save(update_fields=['cell_dropdowns'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_notification_recipient_read_index'),
    ]

    operations = [
        migrations.RunPython(column_dropdowns_only, migrations.RunPython.noop),
    ]
