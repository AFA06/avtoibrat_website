import secrets
import json
import mimetypes
import os
import re
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import check_password
from django.http import JsonResponse, FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.contrib.auth import get_user_model
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST, require_http_methods, require_safe
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum, F, ExpressionWrapper, DurationField

from .leaderboard import PERIODS, build as build_leaderboard
from .animation_scenarios import scenario_for
from . import real_exam
from .models import (
    TeamMember, Testimonial, FAQ, SchoolProfile, Course,
    ContactMessage, PdfMaterial, RoadSignCategory, RoadSign,
    ContactPerson, TestSession, Question, TestCategory,
    Answer, UserAnswer, SavedQuestion, UserDevice, StatisticsReset, Topic, get_device_id, normalize_phone,
    DEVICE_COOKIE
)

from . import lockout
from .public_site import CATEGORIES, CONTACT_TOPICS, handle_consult_form, handle_contact_form
from .road_signs import ordered_categories, sorted_signs
from . import journey, legal, review, topic_tests
from .marathon import MINUTES_PER_QUESTION

User = get_user_model()

CONTENT_LANGUAGES = tuple(code for code, _ in User.GROUP_LANGUAGE_CHOICES)


def _content_language(user, requested=None):
    """The language of questions and answers: what the student picked in the test, else their group's."""
    return requested if requested in CONTENT_LANGUAGES else user.group_language


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
    """Public home page: the school, courses and prices, the exam platform and a sign-up form."""
    form_errors, form_values = {}, {}
    if request.method == "POST":
        ok, form_errors, form_values = handle_consult_form(request.POST)
        if ok:
            messages.success(request, _("Rahmat! So‘rovingiz qabul qilindi — tez orada sizga qo‘ng‘iroq qilamiz."))
            return redirect(reverse("home") + "#apply")

    courses = list(Course.objects.filter(is_active=True))
    return render(request, "index.html", {
        "school": SchoolProfile.current(),
        "courses": courses,
        "taught": {course.category for course in courses},
        "team_members": TeamMember.objects.all()[:4],
        "testimonials": Testimonial.objects.all()[:3],
        "faqs": FAQ.objects.filter(is_active=True)[:5],
        "form_errors": form_errors,
        "form_values": form_values,
        "categories": CATEGORIES,
    }, status=400 if form_errors else 200)


LEGAL_PAGES = {
    "terms": ("terms", _("Foydalanish shartlari")),
    "guide": ("guide", _("Foydalanish yo‘riqnomasi")),
}
LEGAL_LANGUAGES = {"uz": "uz", "uz-kr": "kr", "ru": "ru"}


def _legal_page(request, page):
    """Terms of use and the user guide: public pages, written separately for each site language."""
    slug, title = LEGAL_PAGES[page]
    lang = LEGAL_LANGUAGES.get(request.LANGUAGE_CODE, "uz")
    # A signed-in student reads the document inside the panel, with the sidebar and a way back.
    in_panel = request.user.is_authenticated and not request.user.is_staff
    return render(request, "legal/panel.html" if in_panel else "legal/page.html", {
        "page": page,
        "title": title,
        "content_template": f"legal/content/{slug}.{lang}.html",
        "terms_version": legal.TERMS_VERSION,
    })


def terms(request):
    return _legal_page(request, "terms")


def guide(request):
    return _legal_page(request, "guide")


def error(request, exception=None):
    """«Dead end» page: the 404 handler, also reachable at /error/."""
    return render(request, "404.html", {"school": SchoolProfile.current()}, status=404)


def contact(request):
    """Contact page: how to reach the school, the people to call, and a «write to us» form."""
    form_errors, form_values = {}, {}
    if request.method == "POST":
        ok, form_errors, form_values = handle_contact_form(request.POST)
        if ok:
            messages.success(request, _("Rahmat! Xabaringiz yuborildi — tez orada javob beramiz."))
            return redirect(reverse("contact") + "#write")

    return render(request, "contact.html", {
        "school": SchoolProfile.current(),
        "contacts": ContactPerson.objects.filter(is_active=True),
        "topics": CONTACT_TOPICS,
        "form_errors": form_errors,
        "form_values": form_values,
    }, status=400 if form_errors else 200)


def faq(request):
    return render(request, "faq.html", {
        "school": SchoolProfile.current(),
        "faqs": FAQ.objects.filter(is_active=True),
    })


def team(request):
    return render(request, "team.html", {
        "school": SchoolProfile.current(),
        "team_members": TeamMember.objects.all(),
    })


LOGIN_ROLES = ("student", "staff")


def _staff_login_next(request):
    source = request.POST if request.method == "POST" else request.GET
    target = source.get("next", "")
    if (
        target.startswith(reverse("admin:index"))
        and target.split("?", 1)[0] != reverse("admin:login")
        and url_has_allowed_host_and_scheme(target, allowed_hosts=set())
    ):
        return target
    return None


def _login_redirect(request, role, **params):
    params["role"] = role
    if role == "staff" and (target := _staff_login_next(request)):
        params["next"] = target
    return redirect(f"{reverse('login')}?{urlencode(params)}")


@never_cache
@require_safe
def admin_login(request):
    if request.user.is_active and request.user.is_staff:
        return redirect(_staff_login_next(request) or "admin:index")
    return _login_redirect(request, "staff")


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


DEVICE_COOKIE_AGE = 2 * 365 * 24 * 3600


def _register_device(request, user, device_id):
    """Remember this browser for the student. False when it would exceed their device limit.

    A device over the limit is not saved, so trying again cannot sneak it in. Staff are not limited.
    """
    device = user.devices.filter(device_id=device_id).first()
    if device:
        device.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        device.save()
        return True
    if not (user.is_staff or user.is_superuser) and user.devices.count() >= user.device_limit:
        return False
    UserDevice.objects.create(
        user=user, device_id=device_id,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        ip_address=request.META.get("REMOTE_ADDR") or "0.0.0.0",
    )
    return True


@never_cache
def login_view(request):
    if request.method == "POST":
        role = request.POST.get("role")
        if role not in LOGIN_ROLES:
            role = "student"

        # Signing in means agreeing to the terms of use: the box on the form must be ticked.
        if not legal.accepted(request.POST):
            return _login_redirect(request, role, error="terms")

        identifier = request.POST.get("username", "").strip()
        username = _username_for_phone(identifier) if role == "student" else identifier
        user = authenticate(
            request,
            username=username,
            password=request.POST.get("password"),
        ) if username else None

        if not user and getattr(request, "inactive_account", False):
            return _login_redirect(request, role, expired=1)
        if not user and username and lockout.locked_for(username):
            return _login_redirect(request, role, error="locked", minutes=lockout.minutes_left(username))
        if not user or (role == "staff" and not user.is_staff):
            return _login_redirect(request, role, error="invalid")

        user.sync_active_status()
        if not user.is_active:
            logout(request)
            request.session.flush()
            return _login_redirect(request, role, expired=1)

        device_id = get_device_id(request) or secrets.token_urlsafe(24)
        if not _register_device(request, user, device_id):
            return _login_redirect(request, role, device_limit=1)

        auth_login(request, user)
        legal.record_acceptance(user)
        destination = (_staff_login_next(request) or "admin:index") if role == "staff" else "dashboard"
        if user.must_change_password:
            request.session["post_password_change"] = destination
            destination = "change_temporary_password"
        response = redirect(destination)
        response.set_cookie(
            DEVICE_COOKIE, device_id, max_age=DEVICE_COOKIE_AGE, httponly=True,
            secure=settings.SESSION_COOKIE_SECURE, samesite="Lax",
        )
        return response

    return render(request, "dashboard/login.html")


@never_cache
@login_required
def change_temporary_password(request):
    user = request.user
    default_destination = "admin:index" if user.is_staff else "dashboard"
    if not user.must_change_password:
        return redirect(default_destination)

    form = SetPasswordForm(user, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        old_hash = user.password
        if check_password(form.cleaned_data["new_password1"], old_hash):
            form.add_error("new_password1", _("Vaqtinchalik paroldan boshqa parol tanlang."))
        else:
            form.save(commit=False)
            updated = User.objects.filter(pk=user.pk, password=old_hash, must_change_password=True).update(
                password=user.password, must_change_password=False,
            )
            if not updated:
                logout(request)
                return redirect("login")
            update_session_auth_hash(request, user)
            return redirect(request.session.pop("post_password_change", default_destination))

    return render(request, "dashboard/change_temporary_password.html", {"form": form})


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
        "journey": journey.build(user),
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
    real_exam.close_expired([user.pk])
    today = timezone.localdate()
    sessions = list(
        TestSession.objects
        .filter(user=user, finished_at__isnull=False)
        .select_related("category", "topic")
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
        duration = s.elapsed_seconds(s.finished_at)  # pauses don't count
        seconds_total += duration
        if finished.date() == today:
            seconds_today += duration
        days_with_tests.add(finished.date())
        if finished.date() in week:
            week[finished.date()]["correct"] += counts["correct"]
            week[finished.date()]["wrong"] += counts["wrong"]
            week[finished.date()]["tests"] += 1
        key = ("topic", s.topic_id) if s.topic_id else ("bilet", s.category_id)
        cat = by_category.setdefault(key, {"name": s.title, "correct": 0, "wrong": 0})
        cat["correct"] += counts["correct"]
        cat["wrong"] += counts["wrong"]
        if len(recent) < 5:
            recent.append({
                "id": s.id,
                "name": s.title,
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
        "saved_count": SavedQuestion.objects.filter(user=user, question__is_archived=False).count(),
        "recent": recent,
        "weak": weak,
        "week_days": week_days,
        "week_has_data": any(d["correct"] or d["wrong"] for d in week_days),
    }


def contact_list(request):
    return render(request, "dashboard/contact-list.html", {
        "school_phone": settings.SCHOOL_CONTACT_PHONE,
        "support_telegram_url": settings.SCHOOL_SUPPORT_TELEGRAM_URL,
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
        "pdfs": PdfMaterial.objects.order_by("title")
    })


@login_required
@xframe_options_sameorigin
def manular_view(request, pk):
    """Show a study PDF inside the page's viewer (a frame of our own site)."""
    pdf = get_object_or_404(PdfMaterial, pk=pk)
    if not os.path.exists(pdf.file.path):
        raise Http404("Fayl topilmadi")
    return FileResponse(open(pdf.file.path, "rb"), content_type="application/pdf")


@login_required
def mavzulashtirilgan(request):
    groups = topic_tests.page_groups(request.user)
    return render(request, "dashboard/mavzulashtirilgan.html", {
        "groups": groups,
        "summary": topic_tests.summary(groups),
        "quick_size": topic_tests.QUICK_SIZE,
        "minutes_per_question": MINUTES_PER_QUESTION,
    })



@login_required
def ohshash_savollar(request):
    """Groups of look-alike questions; each row shows the result of its last finished attempt."""
    categories = list(TestCategory.objects.filter(aktiv=True, show_in_ohshash=True).order_by("tartib"))
    latest = _latest_practice_runs(request.user, categories, source="ohshash")
    groups = []
    for cat in categories:
        total = cat.question_count
        group = {"id": cat.id, "nomi": cat.nomi, "total": total, "started": cat.id in latest}
        if cat.id in latest:
            _, (correct, wrong) = latest[cat.id]
            group.update(
                correct=correct,
                wrong=wrong,
                empty=max(total - correct - wrong, 0),
                percent=round(correct * 100 / total) if total else 0,
            )
        groups.append(group)

    done = [g for g in groups if g["started"]]
    return render(request, "dashboard/ohshash-savollar.html", {
        "groups": groups,
        "done_count": len(done),
        "mastered_count": sum(1 for g in done if g["percent"] == 100),
        "avg_percent": round(sum(g["percent"] for g in done) / len(done)) if done else None,
    })


SAVED_TEST_SIZE = 20


@login_required
def saqlangan(request):
    saved = (
        SavedQuestion.objects
        .filter(user=request.user, question__is_archived=False)
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
        .filter(user=request.user, question__is_archived=False)
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



def _latest_practice_runs(user, categories, **filters):
    """Map each category ID to its latest finished session and answer counts."""
    latest = {}
    for session in (
        TestSession.objects
        .filter(user=user, category__in=categories, test_kind="shablon", finished_at__isnull=False, **filters)
        .order_by("-finished_at", "-id")
        .only("category_id", "started_at", "finished_at", "paused_at", "paused_seconds")
    ):
        latest.setdefault(session.category_id, session)
    session_ids = [session.id for session in latest.values()]
    counts = {
        row["session_id"]: (row["correct"], row["wrong"])
        for row in UserAnswer.objects.filter(session_id__in=session_ids).values("session_id").annotate(
            correct=Count("id", filter=Q(is_correct=True)),
            wrong=Count("id", filter=Q(is_correct=False, selected_answer__isnull=False)),
        )
    }
    return {
        category_id: (session, counts.get(session.id, (0, 0)))
        for category_id, session in latest.items()
    }


def _finished_duration_display(session):
    elapsed = session.elapsed_seconds(session.finished_at) if session.finished_at else 0
    minutes, seconds = divmod(elapsed, 60)
    return f"{minutes:02d}:{seconds:02d}"


@login_required
def shablon_test(request):
    categories = list(TestCategory.objects.filter(aktiv=True, show_in_shablon=True))

    latest = _latest_practice_runs(request.user, categories)

    kategoriyalar = []
    for cat in categories:
        has_started = cat.id in latest
        if has_started:
            session, (correct, wrong) = latest[cat.id]
            empty = max(cat.question_count - correct - wrong, 0)
            percent = round(correct * 100 / cat.question_count) if cat.question_count else 0
            duration_display = _finished_duration_display(session)
        else:
            correct = wrong = empty = percent = duration_display = None
        kategoriyalar.append({
            "id": cat.id,
            "nomi": cat.nomi,
            "has_started": has_started,
            "correct": correct,
            "wrong": wrong,
            "empty": empty,
            "percent": percent,
            "duration_display": duration_display,
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



@login_required
@require_POST
def clear_real_statistics(request):
    """Wipe the student's real-exam history only; practice tests stay."""
    sessions = TestSession.objects.filter(user=request.user, test_kind="real")
    answers = UserAnswer.objects.filter(session__in=sessions)
    StatisticsReset.objects.create(user=request.user, tests=sessions.count(), answers=answers.count())
    answers.delete()
    sessions.delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
@transaction.atomic
def clear_topic_statistics(request):
    sessions = TestSession.objects.filter(user=request.user, source=topic_tests.SOURCE)
    StatisticsReset.objects.create(
        user=request.user,
        tests=sessions.count(),
        answers=UserAnswer.objects.filter(session__in=sessions).count(),
        topic_only=True,
    )
    sessions.delete()
    return redirect("mavzulashtirilgan")


def _create_test_session(user, category, test_kind, source="shablon"):
    """Create a session with a fixed, randomly-picked, ordered question set."""
    question_ids = list(
        Question.objects
        .filter(kategoriya=category, is_archived=False)
        .order_by("?")
        .values_list("id", flat=True)[:category.question_count]
    )

    if not question_ids:
        return None

    session = TestSession.objects.create(
        user=user,
        category=category,
        test_kind=test_kind,
        source=source,
        started_at=timezone.now(),
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
    if session is None:
        return redirect("journey" if request.GET.get("from") == "journey" else "shablon_test")
    if request.GET.get("from") == "journey":
        # The result of a bilet started on the season road is shown on the road itself.
        request.session[journey.RUN_KEY] = session.id
    return redirect("test_page", session_id=session.id)


@login_required
def start_mavzu_test(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id, aktiv=True)
    try:
        session = topic_tests.start(request.user, topic, request.GET.get("mode", "quick"))
    except ValueError:
        return redirect("mavzulashtirilgan")
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
    if session is None:
        return redirect("ohshash_savollar")
    return redirect("test_page", session_id=session.id)


@login_required
def real_imtihon(request):
    return render(request, "dashboard/real-imtihon.html", {
        "options": real_exam.options(),
        "history": real_exam.history(request.user),
    })


@login_required
def start_real_exam(request, size):
    try:
        session = real_exam.start(request.user, size)
    except ValueError:
        return redirect("real_imtihon")
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
    return session.remaining_seconds


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

    saved_ids = set(
        SavedQuestion.objects
        .filter(user=request.user, question__in=ordered_questions)
        .values_list("question_id", flat=True)
    )

    # Every language is sent so the student can switch inside the test without a reload.
    questions_data = [
        {
            "id": q.id,
            "image": q.rasm.url if q.rasm else None,
            "saved": q.id in saved_ids,
            "languages": {
                lang: {
                    "text": q.get_text(lang),
                    "answers": [{"id": a.id, "text": a.get_text(lang)} for a in q.answers_for(lang)],
                    # Only the fact that a voice explanation exists; the file itself is served after a mistake.
                    "has_explanation": bool(q.explanation_for(lang)),
                }
                for lang in CONTENT_LANGUAGES
            },
        }
        for q in ordered_questions
    ]
    questions_by_id = {q.id: q for q in ordered_questions}

    user_answers = UserAnswer.objects.filter(session=session)
    answered_data = {
        ua.question_id: {
            "selected": ua.selected_answer_id,
            "correct": _correct_answer_ids(questions_by_id[ua.question_id]),
            "is_correct": ua.is_correct,
            "animation_scenario": (
                scenario_for(questions_by_id[ua.question_id])
                if session.test_kind == "shablon" and session.source == "shablon"
                else None
            ),
        }
        for ua in user_answers
    }

    size = len(session.question_order)
    passing_correct = size - real_exam.max_mistakes(size) + 1 if session.test_kind == "real" and size else 0
    return render(request, "exam/exam.html", {
        "session": session,
        "practice": session.test_kind == "shablon",
        "passing_correct": passing_correct,
        "remaining_seconds": remaining,
        "questions_data": questions_data,
        "answered_data": answered_data,
        "content_languages": CONTENT_LANGUAGES,
        "default_language": request.user.group_language,
    })


def _correct_answer_ids(question):
    """The right answer's id in each language (a language may leave some options out)."""
    return {
        lang: getattr(question.correct_answer_for(lang), "id", None)
        for lang in CONTENT_LANGUAGES
    }


@require_POST
@login_required
def pause_test(request, session_id):
    """Marathon pause: action=pause stops the clock and hides the test, action=resume starts it again."""
    session = get_object_or_404(TestSession, id=session_id, user=request.user)
    if session.finished_at:
        return JsonResponse({"error": "finished"}, status=409)
    if not session.can_pause:
        return JsonResponse({"error": "not_allowed"}, status=403)
    if request.POST.get("action") == "resume":
        session.resume()
    else:
        session.pause()
    return JsonResponse({"paused": session.is_paused, "remaining_seconds": session.remaining_seconds})


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

    if session.is_paused:
        return JsonResponse({"error": "paused"}, status=409)

    grace_seconds = 5
    if session.elapsed_seconds() > session.time_limit_seconds + grace_seconds:
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

    try:
        # A double tap or a retried request can race past the check above; the unique
        # (session, question) constraint keeps one answer and the other gets the same reply.
        with transaction.atomic():
            user_answer = UserAnswer.objects.create(
                session=session,
                question=question,
                selected_answer=answer,
                is_correct=answer.togri,
                answered_at=timezone.now(),
            )
    except IntegrityError:
        return JsonResponse({"error": "already_answered"}, status=409)

    exam_failed = False
    if session.test_kind == "real" and not user_answer.is_correct:
        mistakes = UserAnswer.objects.filter(session=session, is_correct=False).count()
        if mistakes >= real_exam.max_mistakes(len(session.question_order)):
            session.finished_at = timezone.now()
            session.save(update_fields=["finished_at"])
            exam_failed = True

    response = {
        "is_correct": user_answer.is_correct,
        "correct_answer_ids": _correct_answer_ids(question),
        "exam_failed": exam_failed,
    }
    if session.test_kind == "shablon" and session.source == "shablon":
        response["animation_scenario"] = scenario_for(question)
    return JsonResponse(response)


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
    duration_display = _finished_duration_display(session)

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
    list_url = reverse(list_url_name)
    if session.test_kind == "real":
        restart_url = reverse("start_real_exam", args=[len(session.question_order) or real_exam.SIZES[0]])
    elif session.source == topic_tests.SOURCE:
        restart_url = (
            reverse("start_mavzu_test", args=[session.topic_id]) + f"?mode={topic_tests.restart_mode(session)}"
            if session.topic_id else reverse("mavzulashtirilgan")
        )
    elif session.source == "marafon" and session.marathon_size:
        # Back to this size's sections, where the student picks the same or the next section.
        restart_url = reverse("marathon_sections", args=[session.marathon_size])
        list_url = restart_url
    elif restart_url_name in RESTART_WITHOUT_CATEGORY:
        restart_url = reverse(restart_url_name)
    else:
        restart_url = reverse(restart_url_name, args=[session.category_id])

    real_result = None
    mistakes = []
    if session.test_kind == "real" and session.finished_at:
        size = len(session.question_order)
        user = session.user
        real_result = {
            "passed": real_exam.passed(size, wrong, answered),
            "name": user.first_name or user.get_full_name() or user.username,
            "allowed": real_exam.max_mistakes(size) - 1,
        }
        mistakes = review.mistakes(session, _content_language(user))

    journey_stage = None
    is_bilet_run = session.test_kind == "shablon" and session.source in ("shablon", "ohshash") and not session.topic_id
    if is_bilet_run and session.finished_at and total >= session.category.question_count:
        stars = journey.stars_for(correct, total)
        journey_stage = {"stars": stars, "marks": "★" * stars}

    return {
        "real_result": real_result,
        "mistakes": mistakes,
        "journey_stage": journey_stage,
        "has_session": True,
        "session": session,
        "category": session.category,
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "empty": empty,
        "score_percent": score_percent,
        "duration_display": duration_display,
        "cells": cells,
        "restart_url": restart_url,
        "list_url": list_url,
        "list_label": list_label,
    }


def _may_hear_explanation(user, question):
    """Only a student who has answered this question wrongly (in a practice test, or in a finished exam)."""
    return UserAnswer.objects.filter(
        Q(session__test_kind="shablon") | Q(session__finished_at__isnull=False),
        session__user=user, question=question, selected_answer__isnull=False, is_correct=False,
    ).exists()


def serve_audio(request, audio):
    """The whole file, or the byte range a browser asks for (Safari will not play audio without ranges)."""
    data = audio.read()
    total = len(data)
    content_type = mimetypes.guess_type(audio.name)[0] or "audio/mpeg"
    match = re.match(r"bytes=(\d*)-(\d*)$", request.headers.get("Range", ""))
    if match and (match[1] or match[2]):
        start = int(match[1]) if match[1] else max(0, total - int(match[2]))
        end = min(int(match[2]), total - 1) if match[1] and match[2] else total - 1
        if start > end or start >= total:
            return HttpResponse(status=416, headers={"Content-Range": f"bytes */{total}"})
        response = HttpResponse(data[start:end + 1], status=206, content_type=content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{total}"
    else:
        response = HttpResponse(data, content_type=content_type)
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "private, max-age=3600"
    return response


@login_required
def question_explanation(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    audio = question.explanation_for(_content_language(request.user, request.GET.get("lang")))
    if not audio or not _may_hear_explanation(request.user, question):
        raise Http404
    with audio.open("rb") as handle:
        return serve_audio(request, handle)


@login_required
def test_result(request, session_id):
    session = get_object_or_404(TestSession, id=session_id, user=request.user)
    if session.finished_at and request.session.get(journey.RUN_KEY) == session.id:
        del request.session[journey.RUN_KEY]
        return redirect(f"{reverse('journey')}?result={session.id}")
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
                "title": sign.display_full_title,
                "image": sign.image.url,
                "description": sign.display_description,
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


