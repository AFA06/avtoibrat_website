"""O‘xshash savollar: which questions are grouped, and how students solve a set."""
from dataclasses import replace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation

from . import journey, similar
from .models import Answer, Question, SimilarGroup, TestCategory, TestSession, TestType, Topic, TopicGroup, UserAnswer
from .similar import Item, plan

User = get_user_model()
RED_CIRCLE = int("1" * 128 + "0" * 128, 2)
TRIANGLE = int("0" * 128 + "1" * 128, 2)


def near(h, bits):
    """`h` with its first `bits` bits flipped: a picture `bits` away."""
    return h ^ int("1" * bits + "0" * (256 - bits), 2)


def sets_of(items):
    return [sorted(s.question_ids) for s in plan(items).sets]


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
                           self.topic.group_id, "signs") for i, q in enumerate(self.questions)]
        self.client.force_login(self.user)

    def test_rebuild_keeps_the_set_and_its_results_when_nothing_changed(self):
        first = similar.rebuild(self.items)
        group = SimilarGroup.objects.get()
        self.assertEqual((first["created"], group.kind, group.collection), (1, "rasm", "signs"))
        second = similar.rebuild(self.items)
        self.assertEqual((second["created"], second["kept"], SimilarGroup.objects.get().id), (0, 1, group.id))
        similar.rebuild(self.items[:1])                          # questions changed: the old set is switched off
        self.assertFalse(SimilarGroup.objects.get(id=group.id).aktiv)

    def test_student_solves_a_set_in_its_order_and_can_restart_it(self):
        similar.rebuild(self.items)
        group = SimilarGroup.objects.get()
        page = self.client.get(reverse("ohshash_savollar"))
        self.assertContains(page, "Belgilar bo‘yicha o‘xshash savollar")
        self.assertContains(page, "Faqat yo‘l belgilari")

        start = self.client.get(reverse("start_ohshash_test", args=[group.id]))
        session = TestSession.objects.get()
        self.assertEqual(start["Location"], reverse("test_page", args=[session.id]))
        self.assertEqual((session.similar_group_id, session.source), (group.id, "ohshash"))
        self.assertEqual(session.question_order, group.question_order)
        self.assertEqual(session.title, "Belgilar bo‘yicha o‘xshash savollar")

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


    def test_two_options_launch_separate_question_pools(self):
        section = TopicGroup.objects.create(slug="ishoralar-va-chiziqlar", nomi_uzb="Ishoralar")
        topic = Topic.objects.create(group=section, slug="svetofor", nomi_uzb="Svetofor")
        scene_items = []
        for i in range(2):
            q = Question.objects.create(test_turi=self.questions[0].test_turi, kategoriya=self.bilet,
                                        mavzu=topic, matn_uzb=f"Svetofor holati {i}", matn_uz_kr="", matn_rus="")
            Answer.objects.create(question=q, matn_uzb="Ha", togri=True)
            scene_items.append(Item(q.id, q.matn_uzb, frozenset({topic.id}), topic.id,
                                    near(TRIANGLE, i * 8), section.id, "situations"))
        similar.rebuild(self.items + scene_items)
        # Signs, situations, and the same scene picture again under «Rasmlar bo‘yicha».
        self.assertEqual(SimilarGroup.objects.filter(aktiv=True).count(), 3)
        page = self.client.get(reverse("ohshash_savollar"))
        self.assertContains(page, "Belgilar bo‘yicha o‘xshash savollar")
        self.assertNotContains(page, "O‘xshash yo‘l vaziyatlari")  # built, but no longer offered on the page
        group = SimilarGroup.objects.get(collection="situations", aktiv=True)
        self.client.get(reverse("start_ohshash_test", args=[group.id]))
        session = TestSession.objects.get()
        self.assertEqual(set(session.question_order), {i.id for i in scene_items})
        self.assertTrue(set(session.question_order).isdisjoint(q.id for q in self.questions))
        self.assertEqual(session.title, "O‘xshash yo‘l vaziyatlari")


class CollectionPlanTests(TestCase):
    def test_two_collections_are_disjoint_and_only_include_matching_questions(self):
        items = [
            Item(1, "Birinchi belgi nimani bildiradi", frozenset({1}), 1, RED_CIRCLE, 1, "signs"),
            Item(2, "Ikkinchi belgi qayerga qo‘yiladi", frozenset({2}), 2, near(RED_CIRCLE, 8), 1, "signs"),
            # A road-sign topic alone must not include an unrelated or missing image.
            Item(3, "Butunlay boshqa belgi nomi", frozenset({1}), 1, TRIANGLE, 1, "signs"),
            Item(4, "Birinchi belgi nimani bildiradi", frozenset({1}), 1, None, 1, "signs"),
            # Same image as a sign, but traffic signals belong to the other test.
            Item(5, "Svetoforning birinchi holati qanday", frozenset({3}), 3, RED_CIRCLE, 2, "situations"),
            Item(6, "Svetoforning boshqa holati qanday", frozenset({3}), 3, near(RED_CIRCLE, 8), 2, "situations"),
            Item(7, "Tibbiy yordam ko‘rsatish tartibi", frozenset({4}), 4, RED_CIRCLE, 8, ""),
            Item(8, "Qoidaga aloqasiz yo‘l vaziyati", frozenset({5}), 5, RED_CIRCLE, 2, "situations"),
        ]
        result = similar.plan(items)
        self.assertEqual({g.collection: set(g.question_ids) for g in result.sets},
                         {"signs": {1, 2}, "situations": {5, 6}, "images": {5, 6, 7, 8}})

    def test_same_picture_set_skips_signs_and_different_pictures(self):
        items = [
            Item(1, "Belgi nima", frozenset({1}), 1, RED_CIRCLE, 1, "signs"),
            Item(2, "Belgi qayerda", frozenset({1}), 1, RED_CIRCLE, 1, "signs"),
            Item(3, "Kim birinchi o‘tadi", frozenset({2}), 2, TRIANGLE, 2, "situations"),
            Item(4, "Qaysi tezlikda yurish mumkin", frozenset({3}), 3, near(TRIANGLE, 6), 3, ""),
            Item(5, "Boshqa rasmli savol", frozenset({2}), 2, RED_CIRCLE, 2, "situations"),
        ]
        images = [g for g in similar.plan(items).sets if g.collection == "images"]
        self.assertEqual([set(g.question_ids) for g in images], [{3, 4}])

    def test_same_answers_set_needs_matching_options_and_different_questions(self):
        yes_no = ((("ha",), "", "", True), (("yoq",), "", "", False))
        cars = ((("qizil", "avtomobil"), "", "", True), (("yashil", "avtomobil"), "", "", False))
        cars_flipped = ((("qizil", "avtomobil"), "", "", False), (("yashil", "avtomobil"), "", "", True))
        items = [
            Item(1, "Qaysi avtomobil birinchi o‘tadi", frozenset({1}), 1, None, 1, "", cars),
            Item(2, "Qaysi avtomobil oxirgi o‘tadi", frozenset({1}), 1, RED_CIRCLE, 1, "", cars_flipped),
            Item(3, "Qaysi avtomobil to‘xtashi kerak", frozenset({2}), 2, None, 1, "", (cars[0],)),
            Item(4, "Ruxsat etiladimi", frozenset({1}), 1, None, 1, "", yes_no),
            Item(5, "Bu ham ruxsat etiladimi", frozenset({1}), 1, None, 1, "", yes_no),
        ]
        answers = [g for g in similar.plan(items).sets if g.collection == "answers"]
        self.assertEqual([set(g.question_ids) for g in answers], [{1, 2}])

    def test_independent_matched_pairs_stay_adjacent_without_topic_padding(self):
        items = [Item(i, f"Savol {i}", frozenset({1}), 1, h, 1, "signs")
                 for i, h in [(1, RED_CIRCLE), (2, near(RED_CIRCLE, 8)),
                              (3, TRIANGLE), (4, near(TRIANGLE, 8))]]
        result = similar.plan(items)
        self.assertEqual(len(result.sets), 1)
        order = result.sets[0].question_ids
        self.assertEqual({frozenset(order[:2]), frozenset(order[2:])}, {frozenset({1, 2}), frozenset({3, 4})})

    def test_exact_duplicates_are_not_repeated(self):
        items = [Item(i, text, frozenset({1}), 1, image, 1, "signs") for i, text, image in
                 [(1, "Bu belgi qanday nomlanadi", RED_CIRCLE),
                  (2, "Bu belgi qanday nomlanadi", RED_CIRCLE),
                  (3, "Mazkur belgining vazifasi nima", near(RED_CIRCLE, 8))]]
        result = similar.plan(items)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(set(result.sets[0].question_ids), {1, 3})

    def test_same_generic_scene_wording_cannot_override_different_pictures(self):
        text = "Chorrahada qaysi avtomobil birinchi bo‘lib harakatlanishi mumkin va nima uchun"
        items = [Item(i, text, frozenset({1}), 1, image, 2, "situations")
                 for i, image in [(1, RED_CIRCLE), (2, TRIANGLE)]]
        self.assertEqual(similar.plan(items).sets, [])

    def test_one_unmatched_question_does_not_become_a_random_test(self):
        self.assertEqual(similar.plan([Item(1, "Yagona belgi", frozenset({1}), 1,
                                          RED_CIRCLE, 1, "signs")]).sets, [])


class DuplicateTests(TestCase):
    def item(self, qid=1, text="Bu yo‘l belgisi nimani bildiradi?", image=RED_CIRCLE, **kwargs):
        return Item(qid, text, frozenset({1}), 1, image, 1, "signs",
                    ((similar.normalized_content("Ha"), True),
                     (similar.normalized_content("Yo‘q"), False)), **kwargs)

    def test_watermark_resize_typography_and_answer_order_do_not_repeat_a_question(self):
        first = self.item()
        copy = replace(first, id=2, text="BU YO'L BELGISI nimani bildiradi!",
                       image=near(RED_CIRCLE, 25), answers=tuple(reversed(first.answers)))
        self.assertEqual(similar.duplicate_ids([first, copy]), {2})

    def test_different_answer_choices_are_kept(self):
        first = self.item()
        other = replace(first, id=2, answers=((similar.normalized_content("Boshqa javob"), True),))
        self.assertEqual(similar.duplicate_ids([first, other]), set())

    def test_different_correct_answer_is_kept(self):
        first = self.item()
        other = replace(first, id=2, answers=tuple((text, not correct) for text, correct in first.answers))
        self.assertEqual(similar.duplicate_ids([first, other]), set())

    def test_numbers_and_negation_are_meaningful_differences(self):
        for text in ("Bu yo‘l belgisi nimani bildirmaydi?", "Bu yo‘l belgisi 20 nimani bildiradi?"):
            self.assertEqual(similar.duplicate_ids([self.item(), self.item(2, text)]), set())
        self.assertNotEqual(similar.normalized_content("A yo‘nalish"), similar.normalized_content("B yo‘nalish"))

    def test_different_pictures_are_kept(self):
        self.assertEqual(similar.duplicate_ids([self.item(), self.item(2, image=TRIANGLE)]), set())

    def test_matching_a_discarded_copy_does_not_discard_a_distinct_question(self):
        first = self.item(image=0)
        middle = replace(first, id=2, image=near(0, 30))
        last = replace(first, id=3, image=near(0, 60))
        self.assertEqual(similar.duplicate_ids([first, middle, last]), {2})
