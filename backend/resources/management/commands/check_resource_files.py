from django.core.management.base import BaseCommand, CommandError

from resources.models import Resource


class Command(BaseCommand):
    help = 'Fail if a saved resource does not have a readable stored PDF.'

    def handle(self, *args, **options):
        missing = []
        for resource in Resource.objects.only('pk', 'file').iterator():
            if not resource.file or not resource.file.name or not resource.file.storage.exists(resource.file.name):
                missing.append((resource.pk, resource.file.name if resource.file else ''))

        if missing:
            examples = ', '.join(f'{resource_id}:{name or "<empty>"}' for resource_id, name in missing[:20])
            raise CommandError(
                f'{len(missing)} resource file(s) are missing from storage. '
                f'First missing records: {examples}'
            )

        self.stdout.write(self.style.SUCCESS('All resource PDF files are present.'))
