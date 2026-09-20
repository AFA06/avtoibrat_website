from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from django.utils import timezone

from .models import Answer, Branch, ContactPerson, Question, StudyGroup, TestCategory, TestSession, TestType, UserAnswer

User = get_user_model()


class ExamEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="student", password="pass12345", unlimited=True)
        self.test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=3)
        self.category = TestCategory.objects.create(
            nomi="Test kategoriya",
            aktiv=True,
            show_in_real=True,
            question_count=3,
            duration_minutes=25,
        )

        self.questions = []
        for i in range(3):
            question = Question.objects.create(
                test_turi=self.test_type,
                kategoriya=self.category,
                matn_uzb=f"Savol {i}",
                matn_uz_kr=f"Савол {i}",
                matn_rus=f"Вопрос {i}",
            )
            Answer.objects.create(question=question, matn_uzb="To'g'ri", matn_uz_kr="Тўғри", matn_rus="Верно", togri=True)
            Answer.objects.create(question=question, matn_uzb="Xato", matn_uz_kr="Хато", matn_rus="Неверно", togri=False)
            self.questions.append(question)

        self.client.force_login(self.user)

    def _start_session(self):
        response = self.client.get(reverse("start_test", args=[self.category.id]))
        self.assertEqual(response.status_code, 302)
        session_id = int(response.url.rstrip("/").split("/")[-1])
        return TestSession.objects.get(id=session_id)

    def test_start_creates_session_with_fixed_question_order(self):
        session = self._start_session()
        self.assertEqual(len(session.question_order), self.category.question_count)
        self.assertEqual(
            set(session.question_order),
            set(session.questions.values_list("id", flat=True)),
        )
        self.assertIsNotNone(session.started_at)

    def test_exam_page_hides_correctness_before_submit(self):
        session = self._start_session()
        response = self.client.get(reverse("test_page", args=[session.id]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertNotIn("togri", content)
        self.assertNotIn('"is_correct"', content)

    def test_submit_correct_and_wrong_answer(self):
        session = self._start_session()
        question = self.questions[0]
        correct = question.javoblar.get(togri=True)

        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id,
            "question_id": question.id,
            "answer_id": correct.id,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_correct"])
        self.assertEqual(data["correct_answer_id"], correct.id)

        question2 = self.questions[1]
        wrong = question2.javoblar.get(togri=False)
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id,
            "question_id": question2.id,
            "answer_id": wrong.id,
        })
        data = response.json()
        self.assertFalse(data["is_correct"])

    def test_submit_answer_rejects_duplicate(self):
        session = self._start_session()
        question = self.questions[0]
        answer = question.javoblar.first()

        self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        self.assertEqual(response.status_code, 409)

    def test_submit_answer_rejects_question_not_in_session(self):
        session = self._start_session()
        other_type = TestType.objects.create(nomi="Boshqa", vaqt_daqiqa=10, savollar_soni=1)
        other_category = TestCategory.objects.create(nomi="Boshqa kategoriya", question_count=1)
        outside_question = Question.objects.create(
            test_turi=other_type,
            kategoriya=other_category,
            matn_uzb="Tashqi savol",
            matn_uz_kr="Ташқи",
            matn_rus="Внешний",
        )
        outside_answer = Answer.objects.create(question=outside_question, matn_uzb="X", matn_uz_kr="X", matn_rus="X", togri=True)

        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id,
            "question_id": outside_question.id,
            "answer_id": outside_answer.id,
        })
        self.assertEqual(response.status_code, 400)

    def test_submit_answer_rejects_after_finish(self):
        session = self._start_session()
        self.client.post(reverse("finish_test", args=[session.id]))

        question = self.questions[0]
        answer = question.javoblar.first()
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        self.assertEqual(response.status_code, 409)

    def test_finish_test_requires_post(self):
        session = self._start_session()
        response = self.client.get(reverse("finish_test", args=[session.id]))
        self.assertEqual(response.status_code, 405)

    def test_finish_test_sets_finished_at_only_once(self):
        session = self._start_session()
        self.client.post(reverse("finish_test", args=[session.id]))
        session.refresh_from_db()
        first_finished_at = session.finished_at
        self.assertIsNotNone(first_finished_at)

        self.client.post(reverse("finish_test", args=[session.id]))
        session.refresh_from_db()
        self.assertEqual(session.finished_at, first_finished_at)

    def test_result_page_counts(self):
        session = self._start_session()
        correct = self.questions[0].javoblar.get(togri=True)
        wrong = self.questions[1].javoblar.get(togri=False)

        self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": self.questions[0].id, "answer_id": correct.id,
        })
        self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": self.questions[1].id, "answer_id": wrong.id,
        })
        self.client.post(reverse("finish_test", args=[session.id]))

        response = self.client.get(reverse("test_result", args=[session.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["correct"], 1)
        self.assertEqual(response.context["wrong"], 1)
        self.assertEqual(response.context["empty"], 1)

    def test_exam_page_redirects_to_result_when_finished(self):
        session = self._start_session()
        session.finished_at = timezone.now()
        session.save(update_fields=["finished_at"])

        response = self.client.get(reverse("test_page", args=[session.id]))
        self.assertRedirects(response, reverse("test_result", args=[session.id]))


class LoginTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="talaba1", password="pass12345", unlimited=True, phone="+998 90 123 45 67"
        )
        self.teacher = User.objects.create_user(
            username="ustoz", password="pass12345", unlimited=True, is_staff=True
        )
        self.url = reverse("login")

    def post(self, identifier, password="pass12345", role="student"):
        return self.client.post(self.url, {"username": identifier, "password": password, "role": role})

    def test_login_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="step-profile"')

    def test_student_logs_in_with_phone_number(self):
        for typed in ("90 123 45 67", "+998901234567", "998 90 123-45-67"):
            with self.subTest(typed=typed):
                self.client.logout()
                response = self.post(typed)
                self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_short_test_phone_number_works(self):
        User.objects.create_user(username="demo", password="Testing", unlimited=True, phone="9999999")
        response = self.post("9999999", password="Testing")
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_student_cannot_log_in_with_username(self):
        response = self.post("talaba1")
        self.assertIn("error=invalid", response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_shared_phone_number_is_not_resolved(self):
        User.objects.create_user(username="talaba2", password="pass12345", unlimited=True, phone="90 123 45 67")
        response = self.post("901234567")
        self.assertIn("error=invalid", response["Location"])

    def test_wrong_password_keeps_selected_role(self):
        response = self.post("ustoz", password="wrong", role="staff")
        self.assertIn("error=invalid", response["Location"])
        self.assertIn("role=staff", response["Location"])
        self.assertTrue(response["Location"].startswith(self.url))

    def test_staff_logs_in_with_username(self):
        response = self.post("ustoz", role="staff")
        self.assertRedirects(response, reverse("admin:index"), fetch_redirect_response=False)

    def test_staff_profile_rejects_student_account(self):
        response = self.post("talaba1", role="staff")
        self.assertIn("error=invalid", response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_profile_does_not_accept_phone_number(self):
        User.objects.filter(pk=self.teacher.pk).update(phone="90 555 44 33")
        response = self.post("905554433", role="staff")
        self.assertIn("error=invalid", response["Location"])

    def test_expired_account_is_sent_back_with_message(self):
        User.objects.filter(pk=self.student.pk).update(unlimited=False)
        response = self.post("90 123 45 67")
        self.assertIn("expired=1", response["Location"])


class UserPhoneValidationTests(TestCase):
    def test_student_requires_phone(self):
        with self.assertRaises(ValidationError) as ctx:
            User(username="talaba", password="x").full_clean(exclude=["password"])
        self.assertIn("phone", ctx.exception.message_dict)

    def test_staff_does_not_require_phone(self):
        User(username="ustoz", password="x", is_staff=True).full_clean(exclude=["password"])

    def test_phone_must_be_unique_regardless_of_format(self):
        User.objects.create_user(username="a", password="x", phone="+998 90 123 45 67")
        with self.assertRaises(ValidationError) as ctx:
            User(username="b", password="x", phone="901234567").full_clean(exclude=["password"])
        self.assertIn("phone", ctx.exception.message_dict)


class ProfileTests(TestCase):
    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        branch = Branch.objects.create(school_name="Avtovoditel", name="Chilonzor filiali")
        teacher = User.objects.create_user(
            username="ustoz", password="x", is_staff=True, first_name="Ibrat", last_name="Karimov"
        )
        self.group = StudyGroup.objects.create(name="52", category="B", branch=branch, teacher=teacher)
        self.student = User.objects.create_user(
            username="talaba", password="x", unlimited=True, phone="9999999",
            first_name="Nigora", last_name="Abdiqaxxorova", group=self.group,
            birth_date="2005-03-18", passport_number="AD 1544442",
            study_start="2026-07-22", study_end="2026-10-09",
        )
        self.url = reverse("profile")

    def test_profile_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_profile_shows_student_data(self):
        self.client.force_login(self.student)
        response = self.client.get(self.url)
        for expected in (
            "Nigora Abdiqaxxorova", "Avtovoditel", "Chilonzor filiali", "B — yengil avtomobil",
            "52", "Ibrat Karimov", "22.07.2026 — 09.10.2026", "18.03.2005", "AD 1544442",
        ):
            with self.subTest(expected=expected):
                self.assertContains(response, expected)

    def test_profile_shows_placeholder_for_missing_data(self):
        bare = User.objects.create_user(username="yangi", password="x", unlimited=True, phone="9990001")
        self.client.force_login(bare)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ma'lumot yo'q", count=8)

    def test_profile_follows_site_language(self):
        self.client.force_login(self.student)
        response = self.client.get("/ru/profile/")
        self.assertContains(response, "Паспортные данные")
        self.assertContains(response, "B — легковой автомобиль")

    def test_profile_offers_no_password_change(self):
        self.client.force_login(self.student)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'type="password"')

    def test_user_menu_links_profile_and_logout(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, f'href="{reverse("profile")}"')
        self.assertContains(response, f'action="{reverse("logout")}"')
        self.assertContains(response, "N.ABDIQAXXOROVA")


class LogoutTests(TestCase):
    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        self.user = User.objects.create_user(username="talaba", password="x", unlimited=True, phone="9999999")
        self.client.force_login(self.user)

    def test_post_logs_out(self):
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_does_not_log_out(self):
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


class StudentProfileFieldTests(TestCase):
    def build(self, **extra):
        return User(username="talaba", password="x", phone="9999999", **extra)

    def test_passport_is_normalised(self):
        user = self.build(passport_number="ad1544442")
        user.full_clean(exclude=["password"])
        self.assertEqual(user.passport_number, "AD 1544442")

    def test_invalid_passport_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.build(passport_number="1234567AD").full_clean(exclude=["password"])
        self.assertIn("passport_number", ctx.exception.message_dict)

    def test_study_end_cannot_precede_start(self):
        with self.assertRaises(ValidationError) as ctx:
            self.build(study_start="2026-10-09", study_end="2026-07-22").full_clean(exclude=["password"])
        self.assertIn("study_end", ctx.exception.message_dict)

    def test_display_name(self):
        self.assertEqual(self.build(first_name="Nigora", last_name="Abdiqaxxorova").display_name, "N.ABDIQAXXOROVA")
        self.assertEqual(self.build().display_name, "talaba")
        self.assertEqual(self.build().initial, "T")


class ForgotLoginTests(TestCase):
    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        self.url = reverse("forgot_login")

    def make_contact(self, **extra):
        data = {"full_name": "Ali Valiyev", "position": "Administrator", "city": "Toshkent", "phone": "+998 90 111 22 33"}
        return ContactPerson.objects.create(**{**data, **extra})

    def test_page_is_public(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_lists_active_contacts_only(self):
        self.make_contact()
        self.make_contact(full_name="Yashirin Shaxs", is_active=False)
        response = self.client.get(self.url)
        self.assertContains(response, "Ali Valiyev")
        self.assertContains(response, 'href="tel:+998901112233"')
        self.assertNotContains(response, "Yashirin Shaxs")

    def test_shows_telegram_link_when_present(self):
        self.make_contact(telegram="https://t.me/avtoibrat")
        self.assertContains(self.client.get(self.url), 'href="https://t.me/avtoibrat"')

    def test_falls_back_to_school_phone_without_contacts(self):
        response = self.client.get(self.url)
        self.assertContains(response, "tel:+998946274111")

    def test_back_link_keeps_selected_profile(self):
        response = self.client.get(self.url, {"role": "staff"})
        self.assertContains(response, f'href="{reverse("login")}?role=staff"')

    def test_back_link_ignores_unknown_profile(self):
        response = self.client.get(self.url, {"role": "<script>"})
        self.assertContains(response, f'href="{reverse("login")}"')
        self.assertNotContains(response, "<script>alert")

    def test_page_follows_site_language(self):
        self.assertContains(self.client.get("/ru/forgot-login/"), "Вернуться ко входу")

    def test_login_page_links_here(self):
        self.assertContains(self.client.get(reverse("login")), f'data-base-url="{self.url}"')


class SidebarTests(TestCase):
    PANEL_PAGES = (
        "dashboard", "shablon_test", "real_imtihon", "mavzulashtirilgan", "ohshash_savollar",
        "saqlangan", "manular", "road_signs", "contact_list", "profile",
    )

    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        self.user = User.objects.create_user(username="talaba", password="x", unlimited=True, phone="9999999")
        self.client.force_login(self.user)

    def test_every_panel_page_uses_the_shared_sidebar_script(self):
        for name in self.PANEL_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, "dashboard/sidebar.js")
                self.assertContains(response, "dashboard/sidebar.css")
                self.assertNotContains(response, 'document.querySelector(".left-sidebar")')
                self.assertContains(response, 'id="togglemenu"')
                self.assertContains(response, 'type="button" class="nav-link button-menu-mobile nav-icon"')

    def test_home_link_is_called_bosh_sahifa(self):
        for name in self.PANEL_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, "<span>Bosh sahifa</span>")
                self.assertNotContains(response, "abinet")

    def test_home_link_follows_site_language(self):
        self.assertContains(self.client.get("/ru/dashboard/"), "<span>Главная страница</span>")
        self.assertContains(self.client.get("/uz-kr/dashboard/"), "<span>Бош саҳифа</span>")

    def test_sidebar_assets_exist(self):
        for path in ("dashboard/sidebar.js", "dashboard/sidebar.css"):
            with self.subTest(path=path):
                self.assertIsNotNone(finders.find(path))

    def test_theme_script_no_longer_controls_the_sidebar(self):
        theme_script = finders.find("assets_dashboard/js/app.js")
        with open(theme_script, encoding="utf-8") as handle:
            self.assertNotIn("enlarge-menu", handle.read())


class ExamModeTests(TestCase):
    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        user = User.objects.create_user(username="talaba", password="x", unlimited=True, phone="9999999")
        test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=2)
        self.category = TestCategory.objects.create(
            nomi="Bilet", aktiv=True, show_in_shablon=True, show_in_real=True,
            show_in_mavzu=True, show_in_ohshash=True, question_count=2, duration_minutes=25,
        )
        for i in range(2):
            question = Question.objects.create(
                test_turi=test_type, kategoriya=self.category,
                matn_uzb=f"Savol {i}", matn_uz_kr=f"Савол {i}", matn_rus=f"Вопрос {i}",
            )
            for j in range(2):
                Answer.objects.create(
                    question=question, matn_uzb=f"J{j}", matn_uz_kr=f"Ж{j}", matn_rus=f"О{j}", togri=(j == 0)
                )
        self.client.force_login(user)

    def exam_html(self, start_url_name):
        start = self.client.get(reverse(start_url_name, args=[self.category.id]))
        return self.client.get(start["Location"]).content.decode()

    def test_practice_tests_use_the_practice_layout(self):
        for start in ("start_shablon_test", "start_mavzu_test", "start_ohshash_test"):
            with self.subTest(start=start):
                html = self.exam_html(start)
                self.assertIn('class="exam--practice"', html)
                self.assertIn("practice: true", html)
                self.assertIn('id="textUpBtn"', html)
                self.assertIn('id="textDownBtn"', html)

    def test_practice_puts_options_left_and_image_right(self):
        html = self.exam_html("start_shablon_test")
        self.assertLess(html.index('id="examOptions"'), html.index('id="examImageBox"'))

    def test_practice_has_no_answer_confirmation(self):
        html = self.exam_html("start_shablon_test")
        self.assertNotIn('id="answerModal"', html)
        self.assertNotIn("Javobni tasdiqlaysizmi", html)

    def test_real_exam_keeps_its_own_layout_and_confirmation(self):
        html = self.exam_html("start_test")
        self.assertNotIn("exam--practice", html)
        self.assertIn("practice: false", html)
        self.assertIn('id="answerModal"', html)
        self.assertNotIn('id="textUpBtn"', html)
        self.assertLess(html.index('id="examImageBox"'), html.index('id="examOptions"'))

    def test_text_size_limits(self):
        with open(finders.find("exam/exam.js"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn("maxLevel: 15", script)
        self.assertIn("minLevel: -9", script)

    def test_text_size_controls_are_translated(self):
        start = self.client.get(reverse("start_shablon_test", args=[self.category.id]))
        html = self.client.get(start["Location"].replace("/uz/", "/ru/")).content.decode()
        self.assertIn("Увеличить текст", html)
        self.assertIn("Уменьшить текст", html)
