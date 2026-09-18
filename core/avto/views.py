from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_POST
from django.db.models import Sum, F, ExpressionWrapper, DurationField
import json
import os

from .models import (
    TeamMember, Story, ConsultRequest, Testimonial, FAQ,
    ContactMessage, PdfMaterial, RoadSignCategory, RoadSign,
    ContactPerson, TestSession, Question, TestCategory,
    Answer, UserAnswer, SavedQuestion, get_device_id
)

User = get_user_model()

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


def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )

        if not user:
            return redirect("/login/?error=invalid")

        user.sync_active_status()
        if not user.is_active:
            logout(request)
            request.session.flush()
            return redirect("/login/?expired=1")

        auth_login(request, user)
        return redirect("dashboard")

    return render(request, "dashboard/login.html")


def forgot_login(request):
    return render(request, "dashboard/forgotlogin.html")


def user_logout(request):
    logout(request)
    return redirect("login")

@login_required
def dashboard(request):
    user = request.user
    user.sync_active_status()

    if not user.is_active:
        logout(request)
        request.session.flush()
        return redirect("/login/?expired=1")

    today = timezone.now().date()

    sessions = TestSession.objects.filter(
        user=user,
        finished_at__isnull=False
    )

    correct_count = UserAnswer.objects.filter(
        session__in=sessions,
        is_correct=True
    ).count()

    durations = sessions.annotate(
        duration=ExpressionWrapper(
            F("finished_at") - F("started_at"),
            output_field=DurationField()
        )
    )

    total_seconds = durations.aggregate(
        total=Sum("duration")
    )["total"]

    total_seconds = total_seconds.total_seconds() if total_seconds else 0

    today_seconds = durations.filter(
        finished_at__date=today
    ).aggregate(
        total=Sum("duration")
    )["total"]

    today_seconds = today_seconds.total_seconds() if today_seconds else 0

    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0:
            return f"{hours} soat {minutes} daqiqa"
        return f"{minutes} daqiqa"

    week_correct = []
    week_wrong = []

    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)

        day_sessions = sessions.filter(finished_at__date=day)

        week_correct.append(
            UserAnswer.objects.filter(
                session__in=day_sessions,
                is_correct=True
            ).count()
        )

        week_wrong.append(
            UserAnswer.objects.filter(
                session__in=day_sessions,
                is_correct=False,
                selected_answer__isnull=False
            ).count()
        )

    return render(request, "dashboard/dashboard.html", {
        "user": user,
        "users_count": User.objects.count(),
        "correct_count": correct_count,
        "today_time": format_time(today_seconds),
        "total_time": format_time(total_seconds),
        "week_correct_json": json.dumps(week_correct),
        "week_wrong_json": json.dumps(week_wrong),
    })



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



def saqlangan(request):
    saved = (
        SavedQuestion.objects
        .filter(user=request.user)
        .select_related("question")
    )

    return render(request, "dashboard/saqlangan.html", {
        "saved_list": saved
    })



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
        else:
            correct = wrong = empty = None

        kategoriyalar.append({
            "id": cat.id,
            "nomi": cat.nomi,
            "has_started": has_started,
            "correct": correct,
            "wrong": wrong,
            "empty": empty,
        })

    return render(request, "dashboard/shablon-test.html", {
        "kategoriyalar": kategoriyalar
    })


@login_required
@require_POST
def clear_statistics(request):
    UserAnswer.objects.filter(session__user=request.user).delete()
    TestSession.objects.filter(user=request.user).delete()
    return JsonResponse({"success": True})



@login_required
def start_shablon_test(request, category_id):
    category = get_object_or_404(
        TestCategory,
        id=category_id,
        aktiv=True,
        show_in_shablon=True
    )

    session = TestSession.objects.create(
        user=request.user,
        category=category,
        test_kind="shablon"
    )

    questions = (
        Question.objects
        .filter(kategoriya=category)
        .prefetch_related("javoblar")
        .order_by("?")[:category.question_count]
    )

    session.questions.set(questions)

    return redirect("shablon_test_panel", session_id=session.id)




@login_required
def test_panel(request, session_id):
    session = get_object_or_404(
        TestSession,
        id=session_id,
        user=request.user,
        test_kind="shablon"
    )

    if not session.started_at:
        session.started_at = timezone.now()
        session.save(update_fields=["started_at"])

    total_seconds = session.category.duration_minutes * 60

    elapsed = int((timezone.now() - session.started_at).total_seconds())
    remaining = max(0, total_seconds - elapsed)

    questions = (
        session.questions
        .all()
        .prefetch_related("javoblar")
        .order_by("id")
    )
    total_questions = questions.count()

    index = int(request.GET.get("index", 0))
    if index >= total_questions:
        return redirect("finish_test", session_id=session.id)

    question = questions[index]

    answers = UserAnswer.objects.filter(session=session)
    answers_map = {
        ua.question_id: ("correct" if ua.is_correct else "wrong")
        for ua in answers
    }

    question_ids = list(questions.values_list("id", flat=True))

    return render(
        request,
        "test_panel/test-panel.html",
        {
            "session": session,
            "question": question,
            "question_id": question.id,
            "index": index,
            "answers_map": answers_map,
            "question_ids": question_ids,
            "remaining_time": remaining,
        }
    )


@login_required
def start_mavzu_test(request, category_id):
    category = get_object_or_404(
        TestCategory,
        id=category_id,
        aktiv=True,
        show_in_mavzu=True
    )

    session = TestSession.objects.create(
        user=request.user,
        category=category,
        test_kind="shablon",
        source="mavzu"      # ✅ MUHIM
    )

    questions = (
        Question.objects
        .filter(kategoriya=category)
        .prefetch_related("javoblar")
        .order_by("?")[:category.question_count]
    )


    session.questions.set(questions)

    return redirect("shablon_test_panel", session_id=session.id)


@login_required
def start_ohshash_test(request, category_id):
    category = get_object_or_404(
        TestCategory,
        id=category_id,
        aktiv=True,
        show_in_ohshash=True
    )

    session = TestSession.objects.create(
        user=request.user,
        category=category,
        test_kind="shablon",
        source="ohshash"     # ✅ MUHIM
    )

    questions = (
        Question.objects
        .filter(kategoriya=category)
        .prefetch_related("javoblar")
        .order_by("?")[:category.question_count]
    )

    session.questions.set(questions)

    return redirect("shablon_test_panel", session_id=session.id)

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

    session = TestSession.objects.create(
        user=request.user,
        category=category,
        test_kind="real"
    )

    return redirect("test_page", session_id=session.id)


@login_required
def test_panel2(request, session_id):
    session = get_object_or_404(
        TestSession,
        id=session_id,
        user=request.user
    )

    if not session.started_at:
        session.started_at = timezone.now()
        session.save(update_fields=["started_at"])

    total_seconds = session.category.duration_minutes * 60

    elapsed = int((timezone.now() - session.started_at).total_seconds())
    remaining = max(0, total_seconds - elapsed)

    if remaining <= 0:
        return redirect("finish_test", session_id=session.id)

    qs = (
        Question.objects
        .filter(kategoriya=session.category)
        .prefetch_related("javoblar")
        .order_by("?")[:session.category.question_count]
    )

    questions = []
    for q in qs:
        questions.append({
            "id": q.id,
            "text": q.get_text(),
            "image": q.rasm.url if q.rasm else None,
            "answers": [
                {
                    "id": a.id,
                    "text": a.get_text(),
                    "is_correct": a.togri
                }
                for a in q.javoblar.all()
            ]
        })

    return render(
        request,
        "sinov_test_panel/test_panel2.html",
        {
            "session": session,
            "questions": questions,
            "remaining_time": remaining,  # ✅ MUHIM
        }
    )


@require_POST
@login_required
def submit_answer(request):
    session = get_object_or_404(
        TestSession,
        id=request.POST.get("session_id"),
        user=request.user
    )

    question = get_object_or_404(
        Question,
        id=request.POST.get("question_id")
    )

    answer = get_object_or_404(
        Answer,
        id=request.POST.get("answer_id"),
        question=question
    )

    UserAnswer.objects.update_or_create(
        session=session,
        question=question,
        defaults={
            "selected_answer": answer,
            "is_correct": answer.togri
        }
    )

    return JsonResponse({"success": True})



@login_required
def finish_test(request, session_id):
    session = get_object_or_404(
        TestSession,
        id=session_id,
        user=request.user
    )

    answers = UserAnswer.objects.filter(session=session)

    correct = answers.filter(is_correct=True).count()
    wrong = answers.filter(
        is_correct=False,
        selected_answer__isnull=False
    ).count()

    answered = answers.filter(selected_answer__isnull=False).count()
    empty = max(session.category.question_count - answered, 0)

    session.finished_at = timezone.now()
    session.save(update_fields=["finished_at"])

    return render(request, "dashboard/result.html", {
        "correct": correct,
        "wrong": wrong,
        "empty": empty,
    })

@login_required
def result(request):
    last_session = (
        TestSession.objects
        .filter(user=request.user, finished_at__isnull=False)
        .order_by("-finished_at")
        .first()
    )

    if not last_session:
        return render(request, "dashboard/result.html", {
            "correct": 0,
            "wrong": 0,
            "empty": 0,
        })

    answers = UserAnswer.objects.filter(session=last_session)

    correct = answers.filter(is_correct=True).count()
    wrong = answers.filter(
        is_correct=False,
        selected_answer__isnull=False
    ).count()

    answered = answers.filter(selected_answer__isnull=False).count()
    empty = max(last_session.category.question_count - answered, 0)

    return render(request, "dashboard/result.html", {
        "correct": correct,
        "wrong": wrong,
        "empty": empty,
    })



def road_signs(request):
    return render(request, "dashboard/road-signs.html", {
        "categories": RoadSignCategory.objects.all()
    })


def road_signs_two(request, category_slug):
    category = get_object_or_404(RoadSignCategory, slug=category_slug)
    return render(request, "dashboard/road-signs-two.html", {
        "category": category,
        "signs": category.signs.all()
    })


def road_signs_descriptions(request, category_slug, sign_slug):
    sign = get_object_or_404(
        RoadSign,
        category__slug=category_slug,
        slug=sign_slug
    )
    return render(request, "dashboard/road-signs-descriptions.html", {
        "sign": sign
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



from .models import UserDevice
from django.utils import timezone

def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )

        if not user:
            return redirect("/login/?error=invalid")

        user.sync_active_status()
        if not user.is_active:
            logout(request)
            request.session.flush()
            return redirect("/login/?expired=1")

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
                return redirect("/login/?device_limit=1")

        auth_login(request, user)
        return redirect("dashboard")

    return render(request, "dashboard/login.html")




@login_required
@require_POST
def delete_saved_question(request):
    sid = request.POST.get("id")
    SavedQuestion.objects.filter(id=sid, user=request.user).delete()
    return JsonResponse({"success": True})




