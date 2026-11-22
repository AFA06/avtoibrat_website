from django.core.management.base import BaseCommand

from avto import similar


class Command(BaseCommand):
    help = "Build the «O‘xshash savollar» sets from question pictures, wording and topics (safe to repeat)."

    def handle(self, *args, **options):
        stats = similar.rebuild()
        self.stdout.write(self.style.SUCCESS(
            f"O‘xshash savollar: {stats['sets']} sets, {stats['questions']} questions "
            f"{stats['by_kind']}; links {stats['links']}; duplicates skipped {stats['duplicates']}; "
            f"new {stats['created']}, kept {stats['kept']}, switched off {stats['retired']}"
        ))
