"""Create the 10 road-sign categories and (optionally) import signs.

    python manage.py import_road_signs                 # categories only
    python manage.py import_road_signs --official      # categories + the 276 official signs (fixtures/road_signs)
    python manage.py import_road_signs path/to/folder  # folder holds signs.json + image files

signs.json is a list of objects:
    {"category": "ogohlantiruvchi-belgilar", "number": "1.1", "title": "Shlagbaumli temir yo'l kesishmasi",
     "description": "…", "title_kr": "…", "description_kr": "…", "image": "1.1.webp"}
With --official, a sign that already exists (same number in its category) is left alone, so a teacher's edits
survive a redeploy; folder imports update existing signs.
"""
import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from avto.models import RoadSign, RoadSignCategory

CATEGORIES = [
    ("ogohlantiruvchi-belgilar", "Ogohlantiruvchi belgilar"),
    ("imtiyoz-belgilari", "Imtiyoz belgilari"),
    ("taqiqlovchi-belgilar", "Taqiqlovchi belgilar"),
    ("buyuruvchi-belgilar", "Buyuruvchi belgilar"),
    ("axborot-ishora-belgilari", "Axborot-ishora belgilari"),
    ("servis-belgilari", "Servis belgilari"),
    ("qoshimcha-axborot-belgilari", "Qo'shimcha axborot belgilari"),
    ("transport-svetoforlari", "Transport svetoforlari"),
    ("piyodalar-svetoforlari", "Piyodalar svetoforlari"),
    ("taniqlik-belgilari", "Transport vositalarining taniqlik belgilari"),
]

CATEGORY_KR = {
    "ogohlantiruvchi-belgilar": "Огоҳлантирувчи белгилар",
    "imtiyoz-belgilari": "Имтиёз белгилари",
    "taqiqlovchi-belgilar": "Тақиқловчи белгилар",
    "buyuruvchi-belgilar": "Буюрувчи белгилар",
    "axborot-ishora-belgilari": "Ахборот-ишора белгилари",
    "servis-belgilari": "Сервис белгилари",
    "qoshimcha-axborot-belgilari": "Қўшимча ахборот белгилари",
    "transport-svetoforlari": "Транспорт светофорлари",
    "piyodalar-svetoforlari": "Пиёдалар светофорлари",
    "taniqlik-belgilari": "Транспорт воситаларининг таниқлик белгилари",
}

# The official signs from the driving-school presentations (I-ilova 1-7): signs.json + one image per sign.
OFFICIAL = Path(__file__).resolve().parents[2] / "fixtures" / "road_signs"

# Slugs of the drawn demo signs the site shipped with before the real ones; removed on import.
DEMO_SLUGS = [
    "11-shlagbaumli-temir-yol-kesishmasi", "12-shlagbaumsiz-temir-yol-kesishmasi", "15-tramvay-yoli-bilan-kesishuv",
    "16-teng-ahamiyatli-yollar-kesishuvi", "21-asosiy-yol", "31-kirish-taqiqlangan", "41-togriga-harakatlanish",
    "51-avtomagistral", "61-birinchi-tibbiy-yordam-punkti", "711-obyektgacha-bolgan-masofa",
]


class Command(BaseCommand):
    help = "Create road-sign categories and import signs (--official, or a folder with signs.json)."

    def add_arguments(self, parser):
        parser.add_argument("folder", nargs="?")
        parser.add_argument("--official", action="store_true", help="import the official signs from fixtures")

    def handle(self, *args, **opts):
        cats = {}
        for order, (slug, title) in enumerate(CATEGORIES, start=1):
            # get_or_create: a redeploy must not undo a teacher's renames or reordering.
            cat, _ = RoadSignCategory.objects.get_or_create(
                slug=slug, defaults={"title": title, "title_kr": CATEGORY_KR.get(slug, ""), "order": order}
            )
            if not cat.title_kr and slug in CATEGORY_KR:
                RoadSignCategory.objects.filter(pk=cat.pk).update(title_kr=CATEGORY_KR[slug])
            cats[slug] = cat
        self.stdout.write(f"{len(cats)} categories ready")

        if opts["official"]:
            self.restored = 0
            with transaction.atomic():
                # Demo signs carry drawn SVG artwork; real signs that reuse a demo slug are kept.
                removed, _ = RoadSign.objects.filter(slug__in=DEMO_SLUGS, image__endswith=".svg").delete()
                added = self._import(OFFICIAL, cats, keep_existing=True)
            self.stdout.write(f"official signs: {added} added, {self.restored} pictures restored, {removed} demo signs removed")

        if opts["folder"]:
            self.restored = 0
            added = self._import(Path(opts["folder"]), cats, keep_existing=False)
            self.stdout.write(f"{added} signs imported")

    def _import(self, folder, cats, keep_existing):
        try:
            items = json.loads((folder / "signs.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CommandError(f"Cannot read {folder}/signs.json: {exc}")
        count = 0
        for n, item in enumerate(items):
            cat = cats.get(item["category"]) or RoadSignCategory.objects.filter(slug=item["category"]).first()
            if not cat:
                raise CommandError(f"Unknown category slug: {item['category']}")
            number = item.get("number", "")
            existing = RoadSign.objects.filter(category=cat, number=number).first() if number else None
            if keep_existing and existing:
                # Keep the teacher's text; only bring back a picture whose file is gone (fresh disk on Render).
                if not existing.image or not existing.image.storage.exists(existing.image.name):
                    image = folder / item["image"]
                    existing.image.save(image.name, ContentFile(image.read_bytes()), save=True)
                    self.restored += 1
                continue
            image = folder / item["image"]
            self._save(cat, item, image.name, image.read_bytes(), n)
            count += 1
        return count

    def _save(self, cat, item, filename, content, order):
        number = item.get("number", "")
        slug = slugify(f"{number}-{item['title']}")[:50] or slugify(item["title"])[:50]
        sign, _ = RoadSign.objects.update_or_create(
            slug=slug,
            defaults={"category": cat, "number": number, "title": item["title"],
                      "description": item.get("description", ""), "title_kr": item.get("title_kr", ""),
                      "description_kr": item.get("description_kr", ""), "order": order},
        )
        if sign.image:
            sign.image.delete(save=False)
        sign.image.save(filename, ContentFile(content), save=True)
