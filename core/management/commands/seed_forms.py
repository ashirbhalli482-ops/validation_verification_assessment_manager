from django.core.management.base import BaseCommand

from core.package_seed import ensure_default_package_seed


class Command(BaseCommand):
    help = 'Seed default package template with sub-packages P1-A through P1-D and forms'

    def handle(self, *args, **options):
        ensure_default_package_seed()
        self.stdout.write(self.style.SUCCESS('Seeded package template, sub-packages, and forms.'))
