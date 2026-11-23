"""The school panel keeps its working sections and retires the old admin UI."""
import re

from django.test import TestCase
from django.urls import reverse

from .models import Branch, ConsultRequest, ContactMessage, Topic, TopicGroup, User


class AdminPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_superuser(username="owner", password="x")
        cls.teacher = User.objects.create_user(username="teacher", is_staff=True, unlimited=True)

    def setUp(self):
        self.client.force_login(self.owner)

    def sidebar_links(self, response):
        self.assertEqual(response.status_code, 200)
        sidebar = response.content.decode().split('id="jazzy-sidebar">', 1)[1].split("</aside>", 1)[0]
        self.assertNotIn("nav-header", sidebar)
        return re.findall(r'<a href="([^"]+)" class="nav-link', sidebar)

    def test_admin_has_only_the_ten_school_sections_on_every_list_page(self):
        sections = (
            "admin:index", "students:list", "groups:list", "express:list", "assignments:list",
            "questions:list", "signs:list", "monitoring:overview", "teachers:list", "admin_leaderboard",
        )
        expected = [reverse(name) for name in sections]
        for url in expected:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(self.sidebar_links(response), expected)
                self.assertContains(response, 'class="nav-link active"', count=1)

    def test_teacher_navigation_keeps_only_their_available_sections(self):
        self.client.force_login(self.teacher)
        sections = ("admin:index", "students:list", "groups:list", "assignments:list", "monitoring:overview", "admin_leaderboard")
        expected = [reverse(name) for name in sections]
        for url in expected:
            with self.subTest(url=url):
                self.assertEqual(self.sidebar_links(self.client.get(url)), expected)
        for name in ("express:list", "questions:list", "signs:list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_retired_pages_cannot_be_opened_or_used_to_delete_data(self):
        for model in (
            "question", "testcategory", "testtype", "testsession", "useranswer", "savedquestion",
            "similargroup", "teammember", "story", "consultrequest", "schoolprofile", "course",
            "testimonial", "faq", "contactmessage", "contactperson", "roadsigncategory", "roadsign",
            "pdfmaterial", "studygroup", "loginlock",
        ):
            with self.subTest(model=model):
                self.assertEqual(self.client.get(f"/admin/avto/{model}/").status_code, 404)
                self.assertEqual(self.client.post(f"/admin/avto/{model}/1/delete/").status_code, 404)
        self.assertEqual(self.client.get("/admin/auth/group/").status_code, 404)

    def test_dashboard_has_no_contact_inbox_or_global_contact_search(self):
        message = ContactMessage.objects.create(name="Old inbox", phone="901234567", subject="Hello", message="Test")
        consult = ConsultRequest.objects.create(first_name="Old consult", phone="901234567")
        for user in (self.owner, self.teacher):
            self.client.force_login(user)
            response = self.client.get(reverse("admin:index"))
            for text in ("Old inbox", "Old consult", "Yangi murojaatlar", "Sahifa boshqaruvi", "search_form"):
                self.assertNotContains(response, text)
        self.assertTrue(ContactMessage.objects.filter(pk=message.pk).exists())
        self.assertTrue(ConsultRequest.objects.filter(pk=consult.pk).exists())

    def test_group_and_question_forms_keep_their_branch_and_topic_helpers(self):
        branch_url = reverse("admin:avto_branch_add")
        topic_url = reverse("admin:avto_topic_add")
        self.assertContains(self.client.get(reverse("groups:create")), f'href="{branch_url}"')
        self.assertContains(self.client.get(reverse("questions:create")), f'href="{topic_url}"')
        self.assertEqual(self.client.get(branch_url).status_code, 200)
        self.assertEqual(self.client.get(topic_url).status_code, 200)
        self.assertEqual(self.client.post(branch_url, {"school_name": "Avto", "name": "New branch"}).status_code, 302)
        self.assertTrue(Branch.objects.filter(school_name="Avto", name="New branch").exists())
        group_url = reverse("admin:avto_topicgroup_add")
        self.assertEqual(self.client.post(group_url, {
            "nomi_uzb": "New section", "nomi_uz_kr": "", "nomi_rus": "", "tartib": 1,
            "slug": "new-section", "icon": "ti-book",
            "topics-TOTAL_FORMS": "0", "topics-INITIAL_FORMS": "0",
            "topics-MIN_NUM_FORMS": "0", "topics-MAX_NUM_FORMS": "1000",
        }).status_code, 302)
        section = TopicGroup.objects.get(slug="new-section")
        self.assertEqual(self.client.post(topic_url, {
            "nomi_uzb": "New topic", "nomi_uz_kr": "", "nomi_rus": "", "tartib": 1,
            "group": section.pk, "slug": "new-topic", "aktiv": "on",
        }).status_code, 302)
        self.assertContains(self.client.get(reverse("questions:create")), "New topic")
        self.assertTrue(Topic.objects.filter(slug="new-topic", group=section).exists())
