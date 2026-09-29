"""Create the 10 road-sign categories and (optionally) import signs from a folder.

    python manage.py import_road_signs                 # categories only
    python manage.py import_road_signs --sample        # categories + a few drawn sample signs
    python manage.py import_road_signs path/to/folder  # folder holds signs.json + image files

signs.json is a list of objects:
    {"category": "ogohlantiruvchi-belgilar", "number": "1.1", "title": "Shlagbaumli temir yo'l kesishmasi",
     "description": "…", "image": "1.1.png"}
Re-running updates existing signs (matched by slug) instead of duplicating them.
"""
import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
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

RED, BLUE, GREEN = "#e3262b", "#1f5fae", "#1e8449"


def _svg(body):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">' + body + "</svg>"
    ).encode()


def _triangle(inner):
    return _svg(
        '<polygon points="100,12 190,178 10,178" fill="#fff" stroke="%s" stroke-width="16" '
        'stroke-linejoin="round"/>%s' % (RED, inner)
    )


SAMPLE = [
    ("ogohlantiruvchi-belgilar", "1.1", "Shlagbaumli temir yo'l kesishmasi",
     "Belgi aholi punktlarida yo'lning temir yo'l kesib o'tgan qismidan 50-100 metr oldin o'rnatiladi. "
     "Shlagbaumli kesishmada harakatni shlagbaum va svetofor tartibga soladi.",
     _triangle('<g fill="#111"><rect x="55" y="105" width="90" height="10"/><rect x="55" y="135" width="90" height="10"/>'
               + "".join(f'<rect x="{x}" y="90" width="8" height="70"/>' for x in (60, 80, 100, 120, 137)) + "</g>")),
    ("ogohlantiruvchi-belgilar", "1.2", "Shlagbaumsiz temir yo'l kesishmasi",
     "Shlagbaumsiz temir yo'l kesishmasi haqida ogohlantiradi. Kesishmadan oldin to'xtab, poyezd yo'qligiga ishonch hosil qiling.",
     _triangle('<g fill="#111"><rect x="80" y="90" width="40" height="45" rx="6"/><circle cx="88" cy="150" r="9"/>'
               '<circle cx="112" cy="150" r="9"/></g>')),
    ("ogohlantiruvchi-belgilar", "1.5", "Tramvay yo'li bilan kesishuv",
     "Yo'lning tramvay izlari bilan kesishgan joyi haqida ogohlantiradi. Tramvayga yo'l bering.",
     _triangle('<g fill="#111"><rect x="65" y="100" width="70" height="40" rx="6"/><rect x="95" y="80" width="10" height="20"/></g>')),
    ("ogohlantiruvchi-belgilar", "1.6", "Teng ahamiyatli yo'llar kesishuvi",
     "Teng ahamiyatli yo'llar kesishmasi. Bunday kesishmada o'ng tomondan kelayotgan transport vositasiga yo'l berish shart.",
     _triangle('<g stroke="#111" stroke-width="14" stroke-linecap="round"><line x1="70" y1="95" x2="130" y2="155"/>'
               '<line x1="130" y1="95" x2="70" y2="155"/></g>')),
    ("imtiyoz-belgilari", "2.1", "Asosiy yo'l",
     "Asosiy yo'ldan ketayotgan haydovchi kesishmada ikkinchi darajali yo'ldan kelayotganlarga nisbatan imtiyozga ega.",
     _svg('<polygon points="100,8 192,100 100,192 8,100" fill="#fff" stroke="#111" stroke-width="8"/>'
          '<polygon points="100,30 170,100 100,170 30,100" fill="#f7e63b"/>')),
    ("taqiqlovchi-belgilar", "3.1", "Kirish taqiqlangan",
     "Ushbu belgi qo'yilgan yo'lga barcha transport vositalarining kirishi taqiqlanadi.",
     _svg(f'<circle cx="100" cy="100" r="92" fill="{RED}"/><rect x="38" y="82" width="124" height="36" fill="#fff"/>')),
    ("buyuruvchi-belgilar", "4.1", "To'g'riga harakatlanish",
     "Faqat ko'rsatilgan yo'nalishda, ya'ni to'g'riga harakatlanishga ruxsat beriladi.",
     _svg(f'<circle cx="100" cy="100" r="92" fill="{BLUE}"/><polygon points="100,35 135,85 112,85 112,160 88,160 88,85 65,85" fill="#fff"/>')),
    ("axborot-ishora-belgilari", "5.1", "Avtomagistral",
     "Avtomagistral boshlanishini bildiradi. Unda harakatlanish maxsus qoidalarga bo'ysunadi.",
     _svg(f'<rect x="30" y="8" width="140" height="184" rx="10" fill="{GREEN}" stroke="#fff" stroke-width="6"/>'
          '<path d="M100 30 L100 170 M70 170 L92 30 M130 170 L108 30" stroke="#fff" stroke-width="12" fill="none"/>')),
    ("servis-belgilari", "6.1", "Birinchi tibbiy yordam punkti",
     "Birinchi tibbiy yordam ko'rsatish punkti joylashganligini bildiradi.",
     _svg(f'<rect x="30" y="8" width="140" height="184" rx="12" fill="{BLUE}"/>'
          '<rect x="55" y="60" width="90" height="90" rx="10" fill="#fff"/>'
          f'<path d="M100 75v60M70 105h60" stroke="{GREEN}" stroke-width="20"/>')),
    ("qoshimcha-axborot-belgilari", "7.1.1", "Obyektgacha bo'lgan masofa",
     "Belgidan xavfli joy yoki obyektgacha bo'lgan masofani ko'rsatadi.",
     _svg('<rect x="10" y="50" width="180" height="100" rx="12" fill="#fff" stroke="#111" stroke-width="6"/>'
          '<text x="100" y="118" font-family="Arial" font-size="56" font-weight="700" text-anchor="middle">300 m</text>')),
]


class Command(BaseCommand):
    help = "Create road-sign categories and import signs (folder with signs.json, or --sample)."

    def add_arguments(self, parser):
        parser.add_argument("folder", nargs="?")
        parser.add_argument("--sample", action="store_true", help="add a few drawn sample signs")

    def handle(self, *args, **opts):
        cats = {}
        for order, (slug, title) in enumerate(CATEGORIES, start=1):
            cat, _ = RoadSignCategory.objects.update_or_create(
                slug=slug, defaults={"title": title, "order": order}
            )
            cats[slug] = cat
        self.stdout.write(f"{len(cats)} categories ready")

        if opts["sample"]:
            for n, (cat_slug, number, title, desc, svg) in enumerate(SAMPLE):
                self._save(cats[cat_slug], number, title, desc, f"{number}.svg", svg, n)
            self.stdout.write(f"{len(SAMPLE)} sample signs saved")

        if opts["folder"]:
            folder = Path(opts["folder"])
            try:
                items = json.loads((folder / "signs.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CommandError(f"Cannot read {folder}/signs.json: {exc}")
            for n, item in enumerate(items):
                cat = cats.get(item["category"]) or RoadSignCategory.objects.filter(
                    slug=item["category"]
                ).first()
                if not cat:
                    raise CommandError(f"Unknown category slug: {item['category']}")
                image = folder / item["image"]
                self._save(cat, item.get("number", ""), item["title"], item.get("description", ""),
                           image.name, image.read_bytes(), n)
            self.stdout.write(f"{len(items)} signs imported")

    def _save(self, cat, number, title, description, filename, content, order):
        slug = slugify(f"{number}-{title}")[:50] or slugify(title)[:50]
        sign, _ = RoadSign.objects.update_or_create(
            slug=slug,
            defaults={"category": cat, "number": number, "title": title,
                      "description": description, "order": order},
        )
        sign.image.save(filename, ContentFile(content), save=True)
