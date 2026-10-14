"""Load the exam bilets (tickets) from avto/fixtures/bilets.json.

    python manage.py import_bilets                # add the bilets that are missing
    python manage.py import_bilets --force        # also rewrite the texts of bilets that already exist
    python manage.py import_bilets --purge-demo   # also delete leftover demo categories

Each bilet becomes a test category "Bilet N" with 20 questions in three languages. Uzbek Latin and
Cyrillic share their answer rows; Russian answers are separate rows, because the Russian text of a
question often lists different options.

A bilet that already holds real questions is left alone, so teacher edits and uploaded pictures
survive a re-run. --force rewrites texts in place and still keeps audio and video.

Pictures live in avto/fixtures/bilet_images as "<bilet>-<question>.webp" (945x530), numbered like the
questions of the Word documents. A picture is attached to a question that has none; --force also
replaces the pictures that are already there.

Every question also names its topic (avto/fixtures/topics.json) for the topic tests. Topics and
groups are created when missing; a question gets its topic only when it has none, so topics a
teacher changed in the admin survive (--force resets them, and the topic names, to the files).
"""
import json
import re
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from avto.models import Answer, Question, TestCategory, TestType, Topic, TopicGroup

DATA_FILE = Path(__file__).resolve().parents[2] / "fixtures" / "bilets.json"
TOPICS_FILE = DATA_FILE.parent / "topics.json"
IMAGE_DIR = DATA_FILE.parent / "bilet_images"
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
            if not item.get("topic"):
                raise CommandError(f"{where}: no topic")
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


def _sync_topics(force):
    """Create the topic groups and topics; returns {slug: Topic}."""
    topics = {}
    for g_order, group in enumerate(json.loads(TOPICS_FILE.read_text(encoding="utf-8")), start=1):
        names = {"nomi_uzb": group["uz"], "nomi_uz_kr": group["kr"], "nomi_rus": group["ru"], "tartib": g_order}
        row, created = TopicGroup.objects.get_or_create(slug=group["slug"], defaults={**names, "icon": group["icon"]})
        if force and not created:
            TopicGroup.objects.filter(pk=row.pk).update(**names, icon=group["icon"])
        for t_order, topic in enumerate(group["topics"], start=1):
            names = {"nomi_uzb": topic["uz"], "nomi_uz_kr": topic["kr"], "nomi_rus": topic["ru"], "tartib": t_order}
            item, created = Topic.objects.get_or_create(slug=topic["slug"], defaults={**names, "group": row})
            if force and not created:
                Topic.objects.filter(pk=item.pk).update(**names, group=row)
            topics[topic["slug"]] = item
    return topics


def _assign_topics(category, bilet, topics, force):
    """Give question N of the bilet the topic named in the data file. Returns how many were set."""
    questions = list(category.question_set.order_by("id"))
    if len(questions) != len(bilet["questions"]):
        return 0
    assigned = 0
    for question, item in zip(questions, bilet["questions"]):
        topic = topics.get(item.get("topic"))
        if topic and (force or question.mavzu_id is None) and question.mavzu_id != topic.id:
            Question.objects.filter(pk=question.pk).update(mavzu=topic)
            assigned += 1
    return assigned


def _attach_images(category, number, force):
    """Give question N of the bilet its picture "<bilet>-<N>.webp". Returns how many were attached."""
    questions = list(category.question_set.order_by("id"))
    if len(questions) != QUESTIONS_PER_BILET:
        return 0
    attached = 0
    for position, question in enumerate(questions, start=1):
        source = IMAGE_DIR / f"{number}-{position}.webp"
        if not source.exists() or (question.rasm and not force):
            continue
        name = f"questions/images/bilet-{number}-{position}.webp"
        storage = question.rasm.storage
        if storage.exists(name):
            storage.delete(name)
        question.rasm.save(f"bilet-{number}-{position}.webp", ContentFile(source.read_bytes()), save=False)
        Question.objects.filter(pk=question.pk).update(rasm=question.rasm.name)
        attached += 1
    return attached


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
        topics = _sync_topics(options["force"])

        if options["purge_demo"]:
            for category in TestCategory.objects.exclude(nomi__in=names):
                if category.question_set.exists() and _is_demo(category):
                    self.stdout.write(f"deleted demo category «{category.nomi}»")
                    category.delete()

        created = rewritten = skipped = pictures = sorted_into_topics = 0
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
            elif existing and len(existing) != len(bilet["questions"]):
                self.stderr.write(f"{name}: has {len(existing)} questions, not rewritten")
                skipped += 1
            else:
                self._write_questions(category, test_type, bilet, existing)
                rewritten += bool(existing)
                created += not existing
            pictures += _attach_images(category, bilet["bilet"], options["force"])
            sorted_into_topics += _assign_topics(category, bilet, topics, options["force"])

        self.stdout.write(
            f"bilets: {created} created, {rewritten} rewritten, {skipped} left as they were; "
            f"{pictures} pictures attached; {sorted_into_topics} questions sorted into {len(topics)} topics"
        )

    def _write_questions(self, category, test_type, bilet, existing):
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
