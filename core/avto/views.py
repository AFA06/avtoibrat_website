import json
import os
import re
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404, HttpResponseRedirect
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Count, Sum, F, ExpressionWrapper, DurationField

from .leaderboard import REAL_EXAM_MAX_MISTAKES, PERIODS, build as build_leaderboard
from .models import (
    TeamMember, Story, ConsultRequest, Testimonial, FAQ,
    ContactMessage, PdfMaterial, RoadSignCategory, RoadSign,
    ContactPerson, TestSession, Question, TestCategory,
    Answer, UserAnswer, SavedQuestion, UserDevice, StatisticsReset, get_device_id, normalize_phone
)

from .road_signs import ordered_categories, sorted_signs

User = get_user_model()

_LANGUAGE_PREFIX_RE = re.compile(
    r"^/(%s)(/|$)" % "|".join(re.escape(code) for code, _ in settings.LANGUAGES)
)


@require_http_methods(["POST"])
def set_site_language(request):
    """Switch the site's UI language and redirect under the new prefix.

    Django's stock set_language view relies on resolve()/reverse() to
    translate the redirect target to the new language prefix. In this
    project that round trip was returning the URL unchanged (confirmed by
    direct testing), so the language never actually switched. Since every
    page here uses a single, fixed language-code prefix (no per-view
    translated path segments), rewriting the prefix directly is simpler
    and reliable.
    """
    language = request.POST.get("language")
    next_url = request.POST.get("next") or "/"

    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"

    if not language or language not in dict(settings.LANGUAGES):
        return HttpResponseRedirect(next_url)

    path = _LANGUAGE_PREFIX_RE.sub("/", next_url, count=1)
    response = HttpResponseRedirect(f"/{language}{path}")
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
    return response


RESTART_URL_NAMES = {
    ("shablon", "shablon"): "start_shablon_test",
    ("shablon", "mavzu"): "start_mavzu_test",
    ("shablon", "ohshash"): "start_ohshash_test",
    ("shablon", "saqlangan"): "start_saqlangan_test",
    ("shablon", "marafon"): "marathon",
    ("real", "shablon"): "start_test",
}

# Restart targets that are plain pages, not «start test for category N».
RESTART_WITHOUT_CATEGORY = ("start_saqlangan_test", "marathon")

LIST_URL_NAMES = {
    ("shablon", "shablon"): "shablon_test",
    ("shablon", "mavzu"): "mavzulashtirilgan",
    ("shablon", "ohshash"): "ohshash_savollar",
    ("shablon", "saqlangan"): "saqlangan",
    ("shablon", "marafon"): "marathon",
    ("real", "shablon"): "real_imtihon",
}

LIST_LABELS = {
    "shablon_test": _("Shablon testlar"),
    "mavzulashtirilgan": _("Mavzulashtirilgan testlar"),
    "ohshash_savollar": _("Oʻxshash savollar"),
    "saqlangan": _("Saqlangan testlar"),
    "marathon": _("Marafon"),
    "real_imtihon": _("Real imtihon"),
}

def index(request):
    team_members = TeamMember.objects.all()
    stories = Story.objects.filter(is_active=True)[:7]
    testimonials = Testimonial.objects.all()[:5]

    if request.method == "POST":
        ConsultRequest.objects.create(
            first_name=request.POST.get("first_name"),
            last_name=request.POST.get("last_name"),
            phone=request.POST.get("phone"),
            message=request.POST.get("message"),
        )
        return redirect("home")

    return render(request, "index.html", {
        "team_members": team_members,
        "stories": stories,
        "testimonials": testimonials,
    })


def error(request):
    return render(request, "404.html")


def contact(request):
    if request.method == "POST":
        ContactMessage.objects.create(
            name=request.POST.get("form_name"),
            phone=request.POST.get("phone"),
            subject=request.POST.get("form_subject"),
            message=request.POST.get("form_message"),
        )
        return redirect("contact")

    return render(request, "contact.html")


def faq(request):
    return render(request, "faq.html", {
        "faqs": FAQ.objects.filter(is_active=True)
    })


def team(request):
    return render(request, "team.html", {
        "team_members": TeamMember.objects.all()
    })


LOGIN_ROLES = ("student", "staff")


def _login_redirect(role, **params):
    params["role"] = role
    return redirect(f"{reverse('login')}?{urlencode(params)}")


def _username_for_phone(phone):
    """Return the username owning this phone number, or None if there is not exactly one."""
    target = normalize_phone(phone)
    if not target:
        return None
    usernames = [
        username
        for username, stored in User.objects.exclude(phone="").values_list("username", "phone")
        if normalize_phone(stored) == target
    ]
    return usernames[0] if len(usernames) == 1 else None


def login_view(request):
    if request.method == "POST":
        role = request.POST.get("role")
        if role not in LOGIN_ROLES:
            role = "student"

        identifier = request.POST.get("username", "").strip()
        username = _username_for_phone(identifier) if role == "student" else identifier
        user = authenticate(
            request,
            username=username,
            password=request.POST.get("password"),
        ) if username else None

        if not user or (role == "staff" and not user.is_staff):
            return _login_redirect(role, error="invalid")

        user.sync_active_status()
        if not user.is_active:
            logout(request)
            request.session.flush()
            return _login_redirect(role, expired=1)

        device_id = get_device_id(request)

        device, created = UserDevice.objects.get_or_create(
            user=user,
            device_id=device_id,
            defaults={
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "ip_address": request.META.get("REMOTE_ADDR"),
            }
        )

        if not created:
            device.last_used = timezone.now()
            device.save(update_fields=["last_used"])
        else:
            devices_count = user.devices.count()
            if devices_count > user.device_limit:
                return _login_redirect(role, device_limit=1)

        auth_login(request, user)
        return redirect("admin:index" if role == "staff" else "dashboard")

    return render(request, "dashboard/login.html")


def forgot_login(request):
    role = request.GET.get("role")
    return render(request, "dashboard/forgotlogin.html", {
        "contacts": ContactPerson.objects.filter(is_active=True),
        "school_phone": settings.SCHOOL_CONTACT_PHONE,
        "back_role": role if role in LOGIN_ROLES else "",
    })


@require_POST
def user_logout(request):
    logout(request)
    return redirect("login")


@login_required
def profile(request):
    student = User.objects.select_related("group__branch", "group__teacher").get(pk=request.user.pk)
    return render(request, "dashboard/profile.html", {"student": student})

@login_required
def dashboard(request):
    user = request.user
    user.sync_active_status()

    if not user.is_active:
        logout(request)
        request.session.flush()
        return redirect("/login/?expired=1")

    return render(request, "dashboard/dashboard.html", {
        "user": user,
        **_student_stats(user),
    })


def _format_duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes = rest // 60
    if hours:
        return f"{hours} {_('soat')} {minutes} {_('daqiqa')}"
    return f"{minutes} {_('daqiqa')}"


def _student_stats(user):
    """Everything the student dashboard shows, computed from finished sessions."""
    today = timezone.localdate()
    sessions = list(
        TestSession.objects
        .filter(user=user, finished_at__isnull=False)
        .select_related("category")
        .order_by("-finished_at")
    )
    session_ids = [s.id for s in sessions]
    answers = list(
        UserAnswer.objects
        .filter(session_id__in=session_ids)
        .values("session_id", "is_correct", "selected_answer_id")
    )

    per_session = {s.id: {"correct": 0, "wrong": 0} for s in sessions}
    for a in answers:
        bucket = per_session[a["session_id"]]
        if a["is_correct"]:
            bucket["correct"] += 1
        elif a["selected_answer_id"]:
            bucket["wrong"] += 1

    total_correct = sum(v["correct"] for v in per_session.values())
    total_wrong = sum(v["wrong"] for v in per_session.values())
    total_questions = sum(len(s.question_order) for s in sessions)
    total_skipped = max(total_questions - total_correct - total_wrong, 0)
    answered = total_correct + total_wrong

    recent, scores, seconds_total, seconds_today = [], [], 0, 0
    by_category = {}
    days_with_tests = set()
    week = {today - timezone.timedelta(days=i): {"correct": 0, "wrong": 0, "tests": 0} for i in range(6, -1, -1)}

    for s in sessions:
        counts = per_session[s.id]
        size = len(s.question_order) or (counts["correct"] + counts["wrong"]) or 1
        percent = round(counts["correct"] * 100 / size)
        scores.append(percent)
        finished = timezone.localtime(s.finished_at)
        duration = max((s.finished_at - s.started_at).total_seconds(), 0) if s.started_at else 0
        seconds_total += duration
        if finished.date() == today:
            seconds_today += duration
        days_with_tests.add(finished.date())
        if finished.date() in week:
            week[finished.date()]["correct"] += counts["correct"]
            week[finished.date()]["wrong"] += counts["wrong"]
            week[finished.date()]["tests"] += 1
        cat = by_category.setdefault(s.category_id, {"name": s.category.nomi, "correct": 0, "wrong": 0})
        cat["correct"] += counts["correct"]
        cat["wrong"] += counts["wrong"]
        if len(recent) < 5:
            recent.append({
                "id": s.id,
                "name": s.category.nomi,
                "percent": percent,
                "correct": counts["correct"],
                "size": size,
                "when": finished,
                "level": "good" if percent >= 90 else "mid" if percent >= 70 else "low",
            })

    # Consecutive study days ending today (or yesterday, so the streak survives until tonight).
    streak, day = 0, today
    if day not in days_with_tests:
        day -= timezone.timedelta(days=1)
    while day in days_with_tests:
        streak += 1
        day -= timezone.timedelta(days=1)

    weak = sorted(
        (
            {**c, "accuracy": round(c["correct"] * 100 / (c["correct"] + c["wrong"]))}
            for c in by_category.values() if c["wrong"] > 0
        ),
        key=lambda c: (c["accuracy"], -c["wrong"]),
    )[:4]

    max_day = max([d["correct"] + d["wrong"] for d in week.values()] + [1])
    labels = [_("DUSH"), _("SESH"), _("CHOR"), _("PAY"), _("JUM"), _("SHAN"), _("YAK")]
    week_days = [
        {
            "label": labels[d.weekday()],
            "date": d,
            "is_today": d == today,
            "correct": v["correct"],
            "wrong": v["wrong"],
            "tests": v["tests"],
            "correct_h": round(v["correct"] * 100 / max_day),
            "wrong_h": round(v["wrong"] * 100 / max_day),
        }
        for d, v in week.items()
    ]

    circumference = 2 * 3.14159 * 52
    accuracy = round(total_correct * 100 / answered) if answered else 0

    return {
        "tests_done": len(sessions),
        "avg_score": round(sum(scores) / len(scores)) if scores else 0,
        "best_score": max(scores) if scores else 0,
        "accuracy": accuracy,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_skipped": total_skipped,
        "donut_dash": round(circumference * accuracy / 100, 1),
        "donut_gap": round(circumference, 1),
        "total_time": _format_duration(seconds_total),
        "today_time": _format_duration(seconds_today),
        "streak": streak,
        "saved_count": SavedQuestion.objects.filter(user=user).count(),
        "recent": recent,
        "weak": weak,
        "week_days": week_days,
        "week_has_data": any(d["correct"] or d["wrong"] for d in week_days),
    }


def contact_list(request):
    contacts = ContactPerson.objects.filter(is_active=True)
    return render(request, "dashboard/contact-list.html", {
        "contacts": contacts
    })


def manular(request):
    download_id = request.GET.get("download")

    if download_id:
        pdf = get_object_or_404(PdfMaterial, id=download_id)
        if not os.path.exists(pdf.file.path):
            raise Http404("Fayl topilmadi")

        return FileResponse(
            open(pdf.file.path, "rb"),
            as_attachment=True,
            filename=f"{pdf.title}.pdf"
        )

    return render(request, "dashboard/manular.html", {
        "pdfs": PdfMaterial.objects.all()
    })


@login_required
def mavzulashtirilgan(request):
    categories_qs = TestCategory.objects.filter(
        aktiv=True,
        show_in_mavzu=True
    ).order_by("tartib")

    categories = []

    for cat in categories_qs:
        last_session = (
            TestSession.objects
            .filter(
                user=request.user,
                category=cat,
                test_kind="shablon",
                source="mavzu",
                finished_at__isnull=False
            )
            .order_by("-finished_at")
            .first()
        )

        has_started = last_session is not None

        if has_started:
            correct = UserAnswer.objects.filter(
                session=last_session,
                is_correct=True
            ).count()

            wrong = UserAnswer.objects.filter(
                session=last_session,
                is_correct=False,
                selected_answer__isnull=False
            ).count()

            answered = correct + wrong
            empty = max(cat.question_count - answered, 0)
        else:
            correct = wrong = empty = None

        categories.append({
            "id": cat.id,
            "nomi": cat.nomi,
            "has_started": has_started,
            "correct": correct,
            "wrong": wrong,
            "empty": empty,
        })

    return render(request, "dashboard/mavzulashtirilgan.html", {
        "categories": categories
    })



@login_required
def ohshash_savollar(request):
    categories_qs = TestCategory.objects.filter(
        aktiv=True,
        show_in_ohshash=True
    ).order_by("tartib")

    categories = []

    for cat in categories_qs:
        last_session = (
            TestSession.objects
            .filter(
                user=request.user,
                category=cat,
                test_kind="shablon",
                source="ohshash",
                finished_at__isnull=False
            )
            .order_by("-finished_at")
            .first()
        )

        has_started = last_session is not None

        if has_started:
            correct = UserAnswer.objects.filter(
                session=last_session,
                is_correct=True
            ).count()

            wrong = UserAnswer.objects.filter(
                session=last_session,
                is_correct=False,
                selected_answer__isnull=False
            ).count()

            answered = correct + wrong
            empty = max(cat.question_count - answered, 0)
        else:
            correct = wrong = empty = None

        categories.append({
            "id": cat.id,
            "nomi": cat.nomi,
            "has_started": has_started,
            "correct": correct,
            "wrong": wrong,
            "empty": empty,
        })

    return render(request, "dashboard/ohshash-savollar.html", {
        "categories": categories
    })



SAVED_TEST_SIZE = 20


@login_required
def saqlangan(request):
    saved = (
        SavedQuestion.objects
        .filter(user=request.user)
        .select_related("question", "question__kategoriya")
    )

    # One container per test (category), in the same order as the Shablon list.
    groups = {}
    for item in saved:
        groups.setdefault(item.question.kategoriya, []).append(item)
    saved_groups = [
        {"category": cat, "items": items}
        for cat, items in sorted(
            groups.items(), key=lambda pair: (pair[0].tartib, pair[0].id)
        )
    ]

    return render(request, "dashboard/saqlangan.html", {
        "saved_groups": saved_groups,
        "saved_count": len(saved),
        "test_size": min(len(saved), SAVED_TEST_SIZE),
    })


@login_required
def start_saqlangan_test(request):
    """Practice test built only from the student's saved questions (max 20, random order)."""
    question_ids = list(
        SavedQuestion.objects
        .filter(user=request.user)
        .order_by("?")
        .values_list("question_id", flat=True)[:SAVED_TEST_SIZE]
    )
    if not question_ids:
        return redirect("saqlangan")

    first = Question.objects.select_related("kategoriya").get(id=question_ids[0])
    session = TestSession.objects.create(
        user=request.user,
        category=first.kategoriya,
        test_kind="shablon",
        source="saqlangan",
        started_at=timezone.now(),
    )
    session.questions.set(question_ids)
    session.question_order = question_ids
    session.save(update_fields=["question_order"])
    return redirect("test_page", session_id=session.id)



@login_required
def shablon_test(request):
    categories_qs = TestCategory.objects.filter(
        aktiv=True,
        show_in_shablon=True
    )

    kategoriyalar = []

    for cat in categories_qs:
        last_session = (
            TestSession.objects
            .filter(
                user=request.user,
                category=cat,
                test_kind="shablon",
                finished_at__isnull=False
            )
            .order_by("-finished_at")
            .first()
        )

        has_started = last_session is not None

        if has_started:
            correct = UserAnswer.objects.filter(
                session=last_session,
                is_correct=True
            ).count()
            wrong = UserAnswer.objects.filter(
                session=last_session,
                is_correct=False,
                selected_answer__isnull=False
            ).count()
            answered = correct + wrong
            empty = max(cat.question_count - answered, 0)
            percent = round(correct * 100 / cat.question_count) if cat.question_count else 0
        else:
            correct = wrong = empty = percent = None

        kategoriyalar.append({
            "id": cat.id,
            "nomi": cat.nomi,
            "has_started": has_started,
            "correct": correct,
            "wrong": wrong,
            "empty": empty,
            "percent": percent,
        })

    return render(request, "dashboard/shablon-test.html", {
        "kategoriyalar": kategoriyalar
    })


@login_required
@require_POST
def clear_statistics(request):
    answers = UserAnswer.objects.filter(session__user=request.user)
    sessions = TestSession.objects.filter(user=request.user)
    StatisticsReset.objects.create(user=request.user, tests=sessions.count(), answers=answers.count())
    answers.delete()
    sessions.delete()
    return JsonResponse({"success": True})



def _create_test_session(user, category, test_kind, source="shablon"):
    """Create a session with a fixed, randomly-picked, ordered question set."""
    session = TestSession.objects.create(
        user=user,
        category=category,
        test_kind=test_kind,
        source=source,
        started_at=timezone.now(),
    )

    question_ids = list(
        Question.objects
        .filter(kategoriya=category)
        .order_by("?")
        .values_list("id", flat=True)[:category.question_count]
    )

    session.questions.set(question_ids)
    session.question_order = question_ids
    session.save(update_fields=["question_order"])

    return session


@login_required
def start_shablon_test(request, category_id):
    category = get_object_or_404(
        TestCategory,
        id=category_id,
        aktiv=True,
        show_in_shablon=True
    )
    session = _create_test_session(request.user, category, "shablon", "shablon")
    return redirect("test_page", session_id=session.id)


@login_required
def start_mavzu_test(request, category_id):
    category = get_object_or_404(
        TestCategory,
        id=category_id,
        aktiv=True,
        show_in_mavzu=True
    )
    session = _create_test_session(request.user, category, "shablon", "mavzu")
    return redirect("test_page", session_id=session.id)


@login_required
def start_ohshash_test(request, category_id):
    category = get_object_or_404(
        TestCategory,
        id=category_id,
        aktiv=True,
        show_in_ohshash=True
    )
    session = _create_test_session(request.user, category, "shablon", "ohshash")
    return redirect("test_page", session_id=session.id)


@login_required
def real_imtihon(request):
    categories_qs = TestCategory.objects.filter(
        aktiv=True,
        show_in_real=True
    )

    categories = []

    for cat in categories_qs:
        last_session = (
            TestSession.objects
            .filter(
                user=request.user,
                category=cat,
                finished_at__isnull=False,
                test_kind="real"
            )
            .order_by("-finished_at")
            .first()
        )

        if last_session:
            correct = UserAnswer.objects.filter(
                session=last_session,
                is_correct=True
            ).count()

            wrong = UserAnswer.objects.filter(
                session=last_session,
                is_correct=False,
                selected_answer__isnull=False
            ).count()

            answered = correct + wrong
            empty = max(cat.question_count - answered, 0)
        else:
            correct = wrong = empty = 0

        categories.append({
            "id": cat.id,
            "count": cat.question_count,
            "correct": correct,
            "wrong": wrong,
            "empty": empty,
        })

    return render(request, "dashboard/real-imtihon.html", {
        "categories": categories
    })

@login_required
def start_test(request, category_id):
    category = get_object_or_404(
        TestCategory,
        id=category_id,
        aktiv=True
    )
    session = _create_test_session(request.user, category, "real")
    return redirect("test_page", session_id=session.id)


def _ordered_session_questions(session):
    questions_by_id = {
        q.id: q
        for q in Question.objects
        .filter(id__in=session.question_order)
        .prefetch_related("javoblar")
    }
    return [
        questions_by_id[qid]
        for qid in session.question_order
        if qid in questions_by_id
    ]



def _remaining_seconds(session):
    total_seconds = session.time_limit_seconds
    elapsed = int((timezone.now() - session.started_at).total_seconds())
    return max(0, total_seconds - elapsed)


@login_required
def test_page(request, session_id):
    session = get_object_or_404(TestSession, id=session_id, user=request.user)

    if session.finished_at:
        return redirect("test_result", session_id=session.id)

    remaining = _remaining_seconds(session)

    if remaining <= 0:
        session.finished_at = timezone.now()
        session.save(update_fields=["finished_at"])
        return redirect("test_result", session_id=session.id)

    ordered_questions = _ordered_session_questions(session)
    exam_lang = request.user.group_language

    correct_answer_map = {
        q.id: next((a.id for a in q.javoblar.all() if a.togri), None)
        for q in ordered_questions
    }

    saved_ids = set(
        SavedQuestion.objects
        .filter(user=request.user, question__in=ordered_questions)
        .values_list("question_id", flat=True)
    )

    questions_data = [
        {
            "id": q.id,
            "text": q.get_text(exam_lang),
            "image": q.rasm.url if q.rasm else None,
            "saved": q.id in saved_ids,
            "answers": [
                {"id": a.id, "text": a.get_text(exam_lang)}
                for a in q.javoblar.all()
            ],
        }
        for q in ordered_questions
    ]

    user_answers = UserAnswer.objects.filter(session=session)
    answered_data = {
        ua.question_id: {
            "selected": ua.selected_answer_id,
            "correct": correct_answer_map.get(ua.question_id),
            "is_correct": ua.is_correct,
        }
        for ua in user_answers
    }

    return render(request, "exam/exam.html", {
        "session": session,
        "practice": session.test_kind == "shablon",
        "remaining_seconds": remaining,
        "questions_data": questions_data,
        "answered_data": answered_data,
    })


@require_POST
@login_required
def submit_answer(request):
    session = get_object_or_404(
        TestSession,
        id=request.POST.get("session_id"),
        user=request.user
    )

    if session.finished_at:
        return JsonResponse({"error": "finished"}, status=409)

    total_seconds = session.time_limit_seconds
    elapsed = (timezone.now() - session.started_at).total_seconds()
    grace_seconds = 5
    if elapsed > total_seconds + grace_seconds:
        return JsonResponse({"error": "time_over"}, status=409)

    try:
        question_id = int(request.POST.get("question_id"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_question"}, status=400)

    if question_id not in session.question_order:
        return JsonResponse({"error": "invalid_question"}, status=400)

    question = get_object_or_404(Question, id=question_id)
    answer = get_object_or_404(
        Answer,
        id=request.POST.get("answer_id"),
        question=question
    )

    if UserAnswer.objects.filter(session=session, question=question).exists():
        return JsonResponse({"error": "already_answered"}, status=409)

    user_answer = UserAnswer.objects.create(
        session=session,
        question=question,
        selected_answer=answer,
        is_correct=answer.togri,
        answered_at=timezone.now(),
    )

    correct_answer = question.javoblar.filter(togri=True).first()

    exam_failed = False
    if session.test_kind == "real" and not user_answer.is_correct:
        mistakes = UserAnswer.objects.filter(session=session, is_correct=False).count()
        if mistakes >= REAL_EXAM_MAX_MISTAKES:
            session.finished_at = timezone.now()
            session.save(update_fields=["finished_at"])
            exam_failed = True

    return JsonResponse({
        "is_correct": user_answer.is_correct,
        "correct_answer_id": correct_answer.id if correct_answer else None,
        "exam_failed": exam_failed,
    })


@login_required
@require_POST
def finish_test(request, session_id):
    session = get_object_or_404(TestSession, id=session_id, user=request.user)

    if not session.finished_at:
        session.finished_at = timezone.now()
        session.save(update_fields=["finished_at"])

    return redirect("test_result", session_id=session.id)


def _result_context(session):
    total = len(session.question_order) or session.category.question_count

    answers = UserAnswer.objects.filter(session=session)
    correct = answers.filter(is_correct=True).count()
    wrong = answers.filter(
        is_correct=False,
        selected_answer__isnull=False
    ).count()
    answered = correct + wrong
    empty = max(total - answered, 0)
    score_percent = round((correct / total) * 100) if total else 0

    duration_seconds = 0
    if session.started_at and session.finished_at:
        duration_seconds = int(
            (session.finished_at - session.started_at).total_seconds()
        )
    minutes, seconds = divmod(max(duration_seconds, 0), 60)

    status_map = {
        ua.question_id: ("correct" if ua.is_correct else "wrong")
        for ua in answers
    }
    cells = [
        {"number": i + 1, "status": status_map.get(qid, "empty")}
        for i, qid in enumerate(session.question_order)
    ]

    restart_url_name = RESTART_URL_NAMES.get(
        (session.test_kind, session.source), "start_shablon_test"
    )
    list_url_name = LIST_URL_NAMES.get(
        (session.test_kind, session.source), "shablon_test"
    )
    list_label = LIST_LABELS.get(list_url_name, LIST_LABELS["shablon_test"])
    restart_url = (
        reverse(restart_url_name)
        if restart_url_name in RESTART_WITHOUT_CATEGORY
        else reverse(restart_url_name, args=[session.category_id])
    )

    return {
        "has_session": True,
        "session": session,
        "category": session.category,
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "empty": empty,
        "score_percent": score_percent,
        "duration_display": f"{minutes:02d}:{seconds:02d}",
        "cells": cells,
        "restart_url": restart_url,
        "list_url_name": list_url_name,
        "list_label": list_label,
    }


@login_required
def test_result(request, session_id):
    session = get_object_or_404(TestSession, id=session_id, user=request.user)
    return render(request, "dashboard/result.html", _result_context(session))


@login_required
def result(request):
    session = (
        TestSession.objects
        .filter(user=request.user, finished_at__isnull=False)
        .order_by("-finished_at")
        .first()
    )

    if not session:
        return render(request, "dashboard/result.html", {"has_session": False})

    return render(request, "dashboard/result.html", _result_context(session))



ROAD_SIGN_MAIN_COUNT = 7


@login_required
def road_signs(request):
    # Categories with no signs yet stay hidden until they have content.
    categories = list(
        ordered_categories()
        .annotate(sign_count=Count("signs"))
        .filter(sign_count__gt=0)
    )
    return render(request, "dashboard/road-signs.html", {
        "main_categories": categories[:ROAD_SIGN_MAIN_COUNT],
        "extra_categories": categories[ROAD_SIGN_MAIN_COUNT:],
    })


@login_required
def road_signs_two(request, category_slug):
    category = get_object_or_404(RoadSignCategory, slug=category_slug)
    signs = sorted_signs(category)
    return render(request, "dashboard/road-signs-two.html", {
        "category": category,
        "signs": signs,
        "signs_data": [
            {
                "title": sign.full_title,
                "image": sign.image.url,
                "description": sign.description,
            }
            for sign in signs
        ],
    })


@login_required
@require_POST
def toggle_save_question(request):
    question_id = request.POST.get("question_id")

    question = get_object_or_404(Question, id=question_id)

    obj, created = SavedQuestion.objects.get_or_create(
        user=request.user,
        question=question
    )

    if not created:
        obj.delete()
        return JsonResponse({"saved": False})

    return JsonResponse({"saved": True})



@login_required
@require_POST
def delete_saved_question(request):
    sid = request.POST.get("id")
    SavedQuestion.objects.filter(id=sid, user=request.user).delete()
    return JsonResponse({"success": True})




