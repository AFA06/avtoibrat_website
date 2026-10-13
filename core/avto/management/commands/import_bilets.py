"""Load the exam bilets (tickets) from avto/fixtures/bilets.json.

    python manage.py import_bilets                # add the bilets that are missing
    python manage.py import_bilets --force        # also rewrite the texts of bilets that already exist
    python manage.py import_bilets --purge-demo   # also delete leftover demo categories

Each bilet becomes a test category "Bilet N" with 20 questions in three languages. Uzbek Latin and
Cyrillic share their answer rows; Russian answers are separate rows, because the Russian text of a
question often lists different options.

A bilet that already holds real questions is left alone, so teacher edits and uploaded pictures
survive a re-run. --force rewrites texts in place and still keeps pictures, audio and video.
"""
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from avto.models import Answer, Question, TestCategory, TestType

DATA_FILE = Path(__file__).resolve().parents[2] / "fixtures" / "bilets.json"
QUESTIONS_PER_BILET = 20
DURATION_MINUTES = 25
# Placeholder questions of the old demo content.
DEMO_TEXT = re.compile(r"^(Bilet \d+ - |Demo savol \d+|Uzb$)")


def _answer_rows(item):
    rows = [
        {"matn_uzb": a["uz"], "matn_uz_kr": a["kr"], "matn_rus": "", "togri": a["correct"]}
        for a in item["answers"]
    ]
    rows += [
        {"matn_uzb": "", "matn_uz_kr": "", "matn_rus": a["ru"], "togri": a["correct"]}
        for a in item["answers_ru"]
    ]
    return rows


def _validate(bilets):
    for bilet in bilets:
        if len(bilet["questions"]) != QUESTIONS_PER_BILET:
            raise CommandError(f"Bilet {bilet['bilet']}: {len(bilet['questions'])} questions")
        for number, item in enumerate(bilet["questions"], start=1):
            where = f"Bilet {bilet['bilet']}, question {number}"
            if not all(item[lang].strip() for lang in ("uz", "kr", "ru")):
                raise CommandError(f"{where}: empty question text")
            for answers in (item["answers"], item["answers_ru"]):
                if len(answers) < 2 or sum(a["correct"] for a in answers) != 1:
                    raise CommandError(f"{where}: needs 2+ answers with exactly one correct")
                if not all(text.strip() for a in answers for key, text in a.items() if key != "correct"):
                    raise CommandError(f"{where}: empty answer text")


def _is_demo(category):
    texts = list(category.question_set.values_list("matn_uzb", flat=True))
    return all(DEMO_TEXT.match(text) for text in texts)


class Command(BaseCommand):
    help = "Create the exam bilets (questions and answers in three languages) from bilets.json."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Rewrite texts of bilets that already exist.")
        parser.add_argument("--purge-demo", action="store_true", help="Delete leftover demo categories.")

    @transaction.atomic
    def handle(self, *args, **options):
        bilets = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        _validate(bilets)
        test_type = TestType.objects.order_by("id").first() or TestType.objects.create(
            nomi="Bilet", vaqt_daqiqa=DURATION_MINUTES, savollar_soni=QUESTIONS_PER_BILET
        )
        names = {f"Bilet {b['bilet']}" for b in bilets}

        if options["purge_demo"]:
            for category in TestCategory.objects.exclude(nomi__in=names):
                if category.question_set.exists() and _is_demo(category):
                    self.stdout.write(f"deleted demo category «{category.nomi}»")
                    category.delete()

        created = rewritten = skipped = 0
        for bilet in bilets:
            name = f"Bilet {bilet['bilet']}"
            category, _ = TestCategory.objects.get_or_create(
                nomi=name,
                defaults={
                    "tartib": bilet["bilet"], "show_in_shablon": True, "show_in_real": True,
                    "question_count": QUESTIONS_PER_BILET, "duration_minutes": DURATION_MINUTES,
                },
            )
            if category.question_set.exists() and _is_demo(category):
                category.question_set.all().delete()
            existing = list(category.question_set.order_by("id"))
            if existing and not options["force"]:
                skipped += 1
                continue
            if existing and len(existing) != len(bilet["questions"]):
                self.stderr.write(f"{name}: has {len(existing)} questions, not rewritten")
                skipped += 1
                continue

            for position, item in enumerate(bilet["questions"]):
                texts = {"matn_uzb": item["uz"], "matn_uz_kr": item["kr"], "matn_rus": item["ru"]}
                rows = _answer_rows(item)
                if existing:
                    question = existing[position]
                    Question.objects.filter(pk=question.pk).update(**texts)
                    current = list(question.javoblar.values("matn_uzb", "matn_uz_kr", "matn_rus", "togri"))
                    if current == rows:
                        continue
                    question.javoblar.all().delete()
                else:
                    question = Question.objects.create(test_turi=test_type, kategoriya=category, **texts)
                Answer.objects.bulk_create(Answer(question=question, **row) for row in rows)
            if existing:
                rewritten += 1
            else:
                created += 1

        self.stdout.write(f"bilets: {created} created, {rewritten} rewritten, {skipped} left as they were")
