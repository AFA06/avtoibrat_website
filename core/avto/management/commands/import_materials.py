"""Load the study PDFs of the «Qo‘llanma» page from avto/fixtures/materials.

    python manage.py import_materials

A material that already exists (same title) is left alone, so PDFs a teacher added or renamed in the
admin survive a re-run.
"""
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from avto.models import PdfMaterial

MATERIALS = (
    ("Yo‘l belgilari", "yol-belgilari.pdf"),
    ("Yo‘l chiziqlari (yo‘l markirovkasi)", "yol-chiziqlari.pdf"),
)
SOURCE = Path(__file__).resolve().parents[2] / "fixtures" / "materials"


class Command(BaseCommand):
    help = "Add the study PDFs to the Qo‘llanma page when they are missing."

    def handle(self, *args, **options):
        added = 0
        for title, name in MATERIALS:
            existing = PdfMaterial.objects.filter(title=title).first()
            if existing:
                # The row survives in Postgres but Render's disk is fresh after a deploy: restore the file.
                if existing.file and not existing.file.storage.exists(existing.file.name):
                    existing.file.save(name, ContentFile((SOURCE / name).read_bytes()))
                    added += 1
                continue
            PdfMaterial(title=title).file.save(name, ContentFile((SOURCE / name).read_bytes()))
            added += 1
        self.stdout.write(f"materials: {added} added")
