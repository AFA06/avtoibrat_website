"""O‘xshash savollar: which questions are grouped, and how students solve a set."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation

from . import journey, similar
from .models import Answer, Question, SimilarGroup, TestCategory, TestSession, TestType, Topic, TopicGroup, UserAnswer
from .similar import MAX_SET, Item, plan

User = get_user_model()
RED_CIRCLE = int("1" * 128 + "0" * 128, 2)
TRIANGLE = int("0" * 128 + "1" * 128, 2)


def near(h, bits):
    """`h` with its first `bits` bits flipped: a picture `bits` away."""
    return h ^ int("1" * bits + "0" * (256 - bits), 2)


def sets_of(items):
    return [sorted(s.question_ids) for s in plan(items).sets]


class PlanTests(TestCase):
    def test_same_picture_is_grouped_even_with_different_words(self):
        items = [Item(1, "Ushbu yo‘l belgisi qanday nomlanadi?", frozenset({1}), 1, RED_CIRCLE),
                 Item(2, "Mazkur belgi nimani taqiqlaydi?", frozenset({2}), 2, near(RED_CIRCLE, 10)),
                 Item(3, "Belgi qayerda o‘rnatiladi?", frozenset({3}), 3, near(RED_CIRCLE, 15))]
        self.assertEqual(sets_of(items), [[1, 2, 3]])

    def test_generic_question_with_different_pictures_is_not_grouped(self):
        items = [Item(i, "Bu yo‘l belgisi:", frozenset({1}), 1, h)
                 for i, h in ((1, RED_CIRCLE), (2, TRIANGLE), (3, near(TRIANGLE, 128)))]
        self.assertEqual(sets_of(items), [])

    def test_lookalike_pictures_need_similar_wording(self):
        lookalike = near(RED_CIRCLE, 30)                               # same shape, not the same sign
        alike = [Item(1, "Ushbu taqiqlovchi belgi nimani bildiradi?", frozenset({1}), 1, RED_CIRCLE),
                 Item(2, "Mazkur taqiqlovchi belgi nimani bildiradi?", frozenset({1}), 1, lookalike),
                 Item(3, "Ushbu taqiqlovchi belgi nimani taqiqlaydi?", frozenset({1}), 1, near(RED_CIRCLE, 25))]
        self.assertEqual(sets_of(alike), [[1, 2, 3]])
        different = [Item(1, "Ushbu taqiqlovchi belgi nimani bildiradi?", frozenset({1}), 1, RED_CIRCLE),
                     Item(2, "Haydovchi qaysi tezlikda harakatlanishi kerak?", frozenset({1}), 1, lookalike)]
        self.assertEqual(sets_of(different), [])

    def test_same_question_style_is_grouped_inside_a_topic_only(self):
        texts = ["Qizil avtomobil chorrahani birinchi bo‘lib kesib o‘tadi:",
                 "Qizil avtomobil chorrahani ikkinchi bo‘lib kesib o‘tadi:",
                 "Qizil avtomobil chorrahani oxirgi bo‘lib kesib o‘tadi:"]
        filler = [Item(10 + i, f"Boshqa savol {w}", frozenset({9}), 9)
                  for i, w in enumerate(["tezlik", "yuk", "odam", "piyoda", "svetofor"])]
        same_topic = [Item(i + 1, t, frozenset({8}), 8) for i, t in enumerate(texts)]
        self.assertEqual(sets_of(same_topic + filler), [[1, 2, 3]])
        other_topics = [Item(i + 1, t, frozenset({i + 1}), i + 1) for i, t in enumerate(texts)]
        self.assertEqual(sets_of(other_topics + filler), [])

    def test_exact_duplicates_are_asked_once(self):
        items = [Item(i, "Ushbu yo‘l belgisi qanday nomlanadi?", frozenset({1}), 1, h)
                 for i, h in ((1, RED_CIRCLE), (2, RED_CIRCLE), (3, near(RED_CIRCLE, 8)), (4, near(RED_CIRCLE, 20)))]
        result = plan(items)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(sorted(result.sets[0].question_ids), [1, 3, 4])

    def test_sets_never_exceed_the_limit_and_short_ones_are_absorbed(self):
        items = [Item(i, f"Savol {i}", frozenset({1}), 1, near(RED_CIRCLE, i % 12), section=1)
                 for i in range(1, 30)]
        items += [Item(100, "Bitta juft savol", frozenset({1}), 1, TRIANGLE, section=1),
                  Item(101, "Ikkinchi juft savol", frozenset({1}), 1, near(TRIANGLE, 5), section=1)]
        result = plan(items)
        self.assertTrue(all(3 <= len(s.question_ids) <= MAX_SET for s in result.sets))
        grouped = sorted(q for s in result.sets for q in s.question_ids)
        self.assertIn(100, grouped)
        self.assertEqual(len(grouped), len(set(grouped)))

    def test_lookalikes_stand_side_by_side(self):
        a, b = RED_CIRCLE, TRIANGLE
        items = [Item(1, "Belgi bir", frozenset({1}), 1, a), Item(2, "Belgi ikki", frozenset({1}), 1, near(b, 3)),
                 Item(3, "Belgi uch", frozenset({1}), 1, near(a, 2)), Item(4, "Belgi to‘rt", frozenset({1}), 1, b)]
        result = plan(items)
        for s in result.sets:
            order = s.question_ids
            pairs = {frozenset(order[i:i + 2]) for i in range(len(order) - 1)}
            self.assertTrue({frozenset({1, 3}), frozenset({2, 4})} & pairs)


class SimilarPageTests(TestCase):
    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        self.user = User.objects.create_user(username="talaba", password="x", unlimited=True, phone="9990001")
        test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=20)
        self.bilet = TestCategory.objects.create(nomi="Bilet 1", aktiv=True, show_in_shablon=True, question_count=3)
        section = TopicGroup.objects.create(slug="belgilar", nomi_uzb="Yo‘l belgilari")
        self.topic = Topic.objects.create(group=section, slug="taqiq", nomi_uzb="Taqiqlovchi belgilar")
        self.questions = []
        for i in range(3):
            q = Question.objects.create(test_turi=test_type, kategoriya=self.bilet, mavzu=self.topic,
                                        matn_uzb=f"Savol {i}", matn_uz_kr=f"Савол {i}", matn_rus=f"Вопрос {i}")
            Answer.objects.create(question=q, matn_uzb="Ha", matn_uz_kr="Ҳа", matn_rus="Да", togri=True)
            Answer.objects.create(question=q, matn_uzb="Yo‘q", matn_uz_kr="Йўқ", matn_rus="Нет", togri=False)
            self.questions.append(q)
        self.items = [Item(q.id, q.matn_uzb, frozenset({self.topic.id}), self.topic.id, near(RED_CIRCLE, i * 3),
                           self.topic.group_id) for i, q in enumerate(self.questions)]
        self.client.force_login(self.user)

    def test_rebuild_keeps_the_set_and_its_results_when_nothing_changed(self):
        first = similar.rebuild(self.items)
        group = SimilarGroup.objects.get()
        self.assertEqual((first["created"], group.kind, group.topic_id), (1, "rasm", self.topic.id))
        second = similar.rebuild(self.items)
        self.assertEqual((second["created"], second["kept"], SimilarGroup.objects.get().id), (0, 1, group.id))
        similar.rebuild(self.items[:1])                          # questions changed: the old set is switched off
        self.assertFalse(SimilarGroup.objects.get(id=group.id).aktiv)

    def test_student_solves_a_set_in_its_order_and_can_restart_it(self):
        similar.rebuild(self.items)
        group = SimilarGroup.objects.get()
        page = self.client.get(reverse("ohshash_savollar"))
        self.assertContains(page, "Taqiqlovchi belgilar · 1")
        self.assertContains(page, "O‘xshash rasmlar")

        start = self.client.get(reverse("start_ohshash_test", args=[group.id]))
        session = TestSession.objects.get()
        self.assertEqual(start["Location"], reverse("test_page", args=[session.id]))
        self.assertEqual((session.similar_group_id, session.source), (group.id, "ohshash"))
        self.assertEqual(session.question_order, group.question_order)
        self.assertEqual(session.title, "Taqiqlovchi belgilar · 1")

        session.finished_at = timezone.now()
        session.save()
        for q in self.questions:
            UserAnswer.objects.create(session=session, question=q, selected_answer=q.javoblar.get(togri=True),
                                      is_correct=True)
        result = self.client.get(reverse("test_result", args=[session.id]))
        self.assertContains(result, f'href="{reverse("start_ohshash_test", args=[group.id])}"')
        self.assertContains(self.client.get(reverse("ohshash_savollar")), "100%")

    def test_a_set_run_does_not_count_as_a_bilet_on_the_journey(self):
        similar.rebuild(self.items)
        self.client.get(reverse("start_ohshash_test", args=[SimilarGroup.objects.get().id]))
        TestSession.objects.update(finished_at=timezone.now())
        self.assertEqual(journey._bilet_runs(self.user, [self.bilet.id]), [])

    def test_switched_off_set_cannot_be_started(self):
        similar.rebuild(self.items)
        SimilarGroup.objects.update(aktiv=False)
        response = self.client.get(reverse("start_ohshash_test", args=[SimilarGroup.objects.get().id]))
        self.assertEqual(response.status_code, 404)
