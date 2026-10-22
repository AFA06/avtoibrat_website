"""Admin panel: «Savollar» — teachers search, add, edit and delete exam questions (/admin/questions/).

Questions and answers are shown exactly as stored: the order never changes here (only students'
exam pages shuffle the options).
"""
import re

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Answer, Question, TestCategory, TestType, Topic, TopicGroup
from .student_views import _page
from .views import serve_audio

PAGE_SIZE = 25
ANSWER_LIMIT = 8
BILET_QUESTION = re.compile(r"^(\d+)\s*[-–./]\s*(\d+)$")  # «10-12» = bilet 10, question 12


def _bilets():
    return TestCategory.objects.annotate(total=Count("question")).order_by("tartib", "id")


def _topics():
    return Topic.objects.select_related("group").order_by("group__tartib", "tartib", "id")


def _topic_choices():
    """(group name, [(topic id, topic name), …]) for <optgroup> selects."""
    groups = {}
    for topic in _topics():
        groups.setdefault(topic.group.name(), []).append((topic.pk, topic.name()))
    return list(groups.items())


def _with_numbers(questions):
    positions = {}
    for question_id, bilet_id in Question.objects.order_by("kategoriya_id", "id").values_list("id", "kategoriya_id"):
        positions.setdefault(bilet_id, []).append(question_id)
    place = {qid: n for ids in positions.values() for n, qid in enumerate(ids, start=1)}
    for question in questions:
        question.number = place.get(question.pk)
    return questions


@staff_member_required
def question_list(request):
    query = request.GET.get("q", "").strip()
    bilet_id = request.GET.get("bilet", "")
    topic_id = request.GET.get("topic", "")
    picture = request.GET.get("picture", "")

    questions = Question.objects.select_related("kategoriya", "mavzu").prefetch_related("extra_topics", "javoblar")
    if query:
        pair = BILET_QUESTION.match(query)
        if pair:
            bilet = TestCategory.objects.filter(nomi__iregex=rf"(^|\D){int(pair[1])}$").first()
            ids = list(Question.objects.filter(kategoriya=bilet).order_by("id").values_list("id", flat=True)) if bilet else []
            number = int(pair[2])
            questions = questions.filter(pk=ids[number - 1] if 0 < number <= len(ids) else 0)
        else:
            questions = questions.filter(
                Q(matn_uzb__icontains=query) | Q(matn_uz_kr__icontains=query) | Q(matn_rus__icontains=query)
            )
    if bilet_id.isdigit():
        questions = questions.filter(kategoriya_id=bilet_id)
    if topic_id == "none":
        questions = questions.filter(mavzu__isnull=True, extra_topics__isnull=True)
    elif topic_id.isdigit():
        questions = questions.filter(Q(mavzu_id=topic_id) | Q(extra_topics=topic_id))
    if picture == "yes":
        questions = questions.exclude(Q(rasm="") | Q(rasm__isnull=True))
    elif picture == "no":
        questions = questions.filter(Q(rasm="") | Q(rasm__isnull=True))

    page = Paginator(questions.distinct().order_by("kategoriya__tartib", "kategoriya_id", "id"), PAGE_SIZE).get_page(request.GET.get("page"))
    _with_numbers(page.object_list)
    return render(request, "admin/questions/list.html", _page(
        request, "Savollar", page=page, query=query, bilet_id=bilet_id, topic_id=topic_id, picture=picture,
        bilets=_bilets(), topic_choices=_topic_choices(), total=Question.objects.count(),
        no_topic=Question.objects.filter(mavzu__isnull=True, extra_topics__isnull=True).distinct().count(),
        filtered=bool(query or bilet_id or topic_id or picture),
    ))


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ("kategoriya", "mavzu", "extra_topics", "matn_uzb", "matn_uz_kr", "matn_rus", "rasm", "audio_uzb")
        labels = {
            "kategoriya": "Bilet", "mavzu": "Asosiy mavzu", "extra_topics": "Qo‘shimcha mavzular",
            "matn_uzb": "Savol — o‘zbekcha (lotin)", "matn_uz_kr": "Савол — ўзбекча (кирилл)",
            "matn_rus": "Вопрос — русский", "rasm": "Savol rasmi",
        }
        help_texts = {
            "mavzu": "Mavzulashtirilgan testlarda savol shu mavzudan chiqadi.",
            "extra_topics": "Savol boshqa mavzularga ham tegishli bo‘lsa, belgilang (ixtiyoriy).",
            "rasm": "Ixtiyoriy. Aniq 945×530 piksel. Rasm bo‘lmasa, savolda AvtoIbrat logotipi ko‘rinadi.",
        }
        widgets = {
            "matn_uzb": forms.Textarea(attrs={"rows": 3}),
            "matn_uz_kr": forms.Textarea(attrs={"rows": 3}),
            "matn_rus": forms.Textarea(attrs={"rows": 3}),
            "extra_topics": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kategoriya"].queryset = TestCategory.objects.order_by("tartib", "id")
        self.fields["kategoriya"].empty_label = None
        self.fields["mavzu"].required = True
        self.fields["mavzu"].empty_label = "— mavzuni tanlang —"
        self.fields["mavzu"].choices = [("", "— mavzuni tanlang —")] + _topic_choices()
        self.fields["extra_topics"].queryset = _topics()
        self.fields["extra_topics"].choices = [(pk, name) for _, items in _topic_choices() for pk, name in items]
        self.fields["rasm"].widget = forms.FileInput(attrs={"accept": "image/*", "data-image-input": ""})
        for name in ("audio_uzb",):
            self.fields[name].widget = forms.FileInput(attrs={"accept": "audio/*", "data-audio-input": ""})

    def clean(self):
        data = super().clean()
        main = data.get("mavzu")
        if main and main in data.get("extra_topics", []):
            data["extra_topics"] = [t for t in data["extra_topics"] if t != main]
        return data


def _read_answers(post, prefix, languages):
    """The posted answer rows of one list: [{"id", <language>: text…, "correct"}]."""
    rows = []
    ids = post.getlist(f"{prefix}_id")
    correct = post.get(f"{prefix}_correct", "")
    keys = {lang: post.getlist(f"{prefix}_{lang}") for lang in languages}
    for index, row_id in enumerate(ids):
        texts = {lang: (keys[lang][index] if index < len(keys[lang]) else "").strip() for lang in languages}
        if not any(texts.values()):
            continue  # an empty row is just an unused slot
        rows.append({"id": int(row_id) if row_id.isdigit() else None, **texts, "correct": correct == str(index)})
    return rows


def _check_answers(rows, languages, label, errors):
    if len(rows) < 2:
        errors.append(f"{label}: kamida 2 ta javob kerak.")
        return
    if any(not row[lang] for row in rows for lang in languages):
        errors.append(f"{label}: har bir javob matni to‘liq (barcha tillarda) yozilishi kerak.")
    if sum(row["correct"] for row in rows) != 1:
        errors.append(f"{label}: to‘g‘ri javobni bitta qilib belgilang.")


def _initial_answers(question):
    """Rows for the two answer lists of an existing question, in stored order."""
    uz, ru = [], []
    for answer in question.javoblar.all():
        if answer.matn_uzb.strip() or answer.matn_uz_kr.strip():
            uz.append({"id": answer.pk, "uz": answer.matn_uzb, "kr": answer.matn_uz_kr, "correct": answer.togri})
        if answer.matn_rus.strip():
            ru.append({"id": answer.pk, "ru": answer.matn_rus, "correct": answer.togri})
    return uz, ru


def _save_answers(question, uz_rows, ru_rows):
    """Update rows in place (so students' answer history keeps pointing at them), add new ones, drop removed ones."""
    existing = {a.pk: a for a in question.javoblar.all()}
    kept = set()
    for row in uz_rows:
        answer = existing.get(row["id"]) if row["id"] not in kept else None
        answer = answer or Answer(question=question)
        answer.matn_uzb, answer.matn_uz_kr, answer.matn_rus, answer.togri = row["uz"], row["kr"], "", row["correct"]
        answer.save()
        kept.add(answer.pk)
    for row in ru_rows:
        answer = existing.get(row["id"]) if row["id"] not in kept else None
        answer = answer or Answer(question=question)
        answer.matn_uzb, answer.matn_uz_kr, answer.matn_rus, answer.togri = "", "", row["ru"], row["correct"]
        answer.save()
        kept.add(answer.pk)
    question.javoblar.exclude(pk__in=kept).delete()


@staff_member_required
def question_form(request, pk=None):
    question = get_object_or_404(Question.objects.prefetch_related("javoblar"), pk=pk) if pk else None
    initial = {}
    if not question:
        initial = {k: request.GET[k] for k in ("kategoriya", "mavzu") if request.GET.get(k, "").isdigit()}
    form = QuestionForm(request.POST or None, request.FILES or None, instance=question, initial=initial)

    if request.method == "POST":
        uz_rows = _read_answers(request.POST, "uz", ("uz", "kr"))
        ru_rows = _read_answers(request.POST, "ru", ("ru",))
        problems = []
        _check_answers(uz_rows, ("uz", "kr"), "O‘zbekcha javoblar", problems)
        _check_answers(ru_rows, ("ru",), "Русские ответы", problems)
        valid = form.is_valid()
        for problem in problems:
            form.add_error(None, problem)
        if valid and not problems:
            with transaction.atomic():
                saved = form.save(commit=False)
                if request.POST.get("remove_picture") and not request.FILES.get("rasm"):
                    saved.rasm = None
                for name in ("audio_uzb",):
                    if request.POST.get(f"remove_{name}") and not request.FILES.get(name):
                        getattr(saved, name).delete(save=False)
                        setattr(saved, name, None)
                if not saved.pk:
                    saved.test_turi = TestType.objects.order_by("id").first() or TestType.objects.create(
                        nomi="Bilet", vaqt_daqiqa=25, savollar_soni=20)
                saved.save()
                form.save_m2m()
                _save_answers(saved, uz_rows, ru_rows)
            messages.success(request, "Savol saqlandi.")
            if request.POST.get("add_another"):
                return redirect(f"{reverse('questions:create')}?kategoriya={saved.kategoriya_id}&mavzu={saved.mavzu_id}")
            return redirect("questions:list")
    elif question:
        uz_rows, ru_rows = _initial_answers(question)
    else:
        uz_rows, ru_rows = [], []

    blank = {"id": "", "uz": "", "kr": "", "ru": "", "correct": False}
    uz_rows = uz_rows + [blank] * max(0, 4 - len(uz_rows))
    ru_rows = ru_rows + [blank] * max(0, 4 - len(ru_rows))
    return render(request, "admin/questions/form.html", _page(
        request, "Savolni tahrirlash" if question else "Yangi savol", form=form, question=question,
        uz_rows=uz_rows, ru_rows=ru_rows, answer_limit=ANSWER_LIMIT,
        bilet_counts={b.pk: b.total for b in _bilets()},
        number=_with_numbers([question])[0].number if question else None,
    ))


@staff_member_required
def question_audio(request, pk, language):
    """Lets a teacher listen to the stored explanation while editing (students use a gated view)."""
    question = get_object_or_404(Question, pk=pk)
    audio = question.audio_rus if language == "ru" else question.audio_uzb
    if not audio:
        raise Http404
    with audio.open("rb") as handle:
        return serve_audio(request, handle)


@staff_member_required
@require_POST
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    question.delete()
    messages.success(request, "Savol o‘chirildi.")
    return redirect("questions:list")
