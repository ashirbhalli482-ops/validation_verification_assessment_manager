from django.core.management.base import BaseCommand

from core.package_seed import ensure_default_package_seed


class Command(BaseCommand):
    help = 'Ensure default package template and sub-packages exist (no sample forms)'

    def handle(self, *args, **options):
        ensure_default_package_seed()
        self.stdout.write(self.style.SUCCESS(
            'Ensured package template and sub-packages (admin-created forms only).',
        ))
