from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.utils import translation, timezone
from .models import User, Question, TestCategory, TestType, Topic, TopicGroup, SimilarGroup, TestSession, UserAnswer
from .question_placement import ordered
from . import marathon, topic_tests, similar
from .views import _create_test_session


class QuestionPlacementTests(TestCase):
    def setUp(self):
        self.addCleanup(translation.activate, translation.get_language())
        self.admin = User.objects.create_user(username='placement-admin', is_staff=True, is_superuser=True, unlimited=True)
        self.student = User.objects.create_user(username='placement-student', unlimited=True)
        self.category = TestCategory.objects.create(nomi='Bilet 1', show_in_shablon=True)
        self.kind = TestType.objects.create(nomi='Bilet', vaqt_daqiqa=25, savollar_soni=20)
        group = TopicGroup.objects.create(slug='placement', nomi_uzb='Qoidalar')
        self.topic = Topic.objects.create(group=group, slug='placement', nomi_uzb='Mavzu')
        self.questions = [Question.objects.create(kategoriya=self.category, test_turi=self.kind, mavzu=self.topic, matn_uzb=f'Question {i}', matn_uz_kr='x', matn_rus='y') for i in range(1,21)]
        self.client.force_login(self.admin)

    def post(self, **over):
        data = dict(kategoriya=self.category.pk, mavzu=self.topic.pk, matn_uzb='New question', matn_uz_kr='Янги', matn_rus='Новый',
                    placement_controls='1', use_in_bilet='on', use_in_topics='on', use_in_mixed='on', auto_similar='on', order_scope='bilet',
                    uz_id=['',''], uz_uz=['A','B'], uz_kr=['А','Б'], uz_correct='0', ru_id=['',''], ru_ru=['Да','Нет'], ru_correct='1')
        data.update(over)
        response = self.client.post(reverse('questions:create'), data)
        return response

    def test_insert_between_12_and_13_and_preserve_started_session(self):
        old = _create_test_session(self.student,self.category,'shablon')
        snapshot = list(old.question_order)
        self.assertEqual(self.post(position=13).status_code,302)
        new = Question.objects.get(matn_uzb='New question')
        expected = [q.pk for q in self.questions]; expected.insert(12,new.pk)
        self.assertEqual(list(ordered(Question.objects.filter(kategoriya=self.category)).values_list('pk',flat=True)),expected)
        old.finished_at=timezone.now();old.save(update_fields=["finished_at"])
        UserAnswer.objects.bulk_create([UserAnswer(session=old,question_id=pk,is_correct=True) for pk in snapshot])
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("shablon_test")).context["kategoriyalar"][0]["percent"],100)
        self.client.force_login(self.admin)
        old.refresh_from_db();self.assertEqual(old.question_order,snapshot)
        self.category.refresh_from_db();self.assertEqual(self.category.question_count,21)
        self.assertEqual(_create_test_session(self.student,self.category,'shablon').question_order,expected)
        self.assertEqual(topic_tests.pick_question_ids(self.student,self.topic,'all'),expected)
        self.assertEqual(marathon.ordered_ids(),expected)
        html=self.client.get(reverse('questions:list'),{'q':'1-13'})
        self.assertEqual([q.pk for q in html.context['page']],[new.pk])

    def test_explicit_destinations_and_optional_topic(self):
        response=self.post(use_in_bilet='',use_in_topics='',auto_similar='',mavzu='')
        self.assertEqual(response.status_code,302)
        new=Question.objects.get(matn_uzb='New question')
        self.assertIn(new,marathon.question_pool())
        self.assertNotIn(new,topic_tests.question_pool(self.topic))
        session=_create_test_session(self.student,self.category,'shablon')
        self.assertNotIn(new.pk,session.question_order)
        self.assertNotIn(new.pk,[item.id for item in similar.load_items()])

    def test_insert_topic_and_bounds(self):
        self.assertEqual(self.post(position=999).status_code,200)
        self.assertFalse(Question.objects.filter(matn_uzb='New question').exists())
        self.assertEqual(self.post(position=5,order_scope='topic').status_code,302)
        new=Question.objects.get(matn_uzb='New question')
        self.assertEqual(topic_tests.pick_question_ids(self.student,self.topic,'all')[4],new.pk)
        self.assertEqual(list(ordered(Question.objects.filter(kategoriya=self.category)).values_list("pk",flat=True)), [q.pk for q in self.questions]+[new.pk])
        self.assertContains(self.client.get(reverse('questions:list'),{'topic':self.topic.pk}),'Shundan keyin qo‘shish (mavzu)')

    def test_manual_set_versions_survive_rebuild(self):
        ids=[q.pk for q in self.questions[:2]]
        plan=similar.PlannedSet(ids,None,'aralash','answers')
        group=SimilarGroup.objects.create(collection='answers',signature=plan.signature,question_order=ids)
        group.questions.set(ids)
        old=TestSession.objects.create(user=self.student,category=self.category,source='ohshash',test_kind='shablon',similar_group=group,question_order=ids)
        self.assertEqual(self.post(collections=[group.pk],collection_position=2).status_code,302)
        new=Question.objects.get(matn_uzb='New question');group.refresh_from_db();self.assertFalse(group.aktiv)
        current=SimilarGroup.objects.get(aktiv=True,is_manual=True)
        self.assertEqual(current.question_order,[ids[0],new.pk,ids[1]])
        with patch('avto.similar.plan',return_value=similar.Plan(sets=[plan])):
            similar.rebuild([])
        expanded = similar.PlannedSet(ids+[new.pk],None,"aralash","answers")
        with patch("avto.similar.plan",return_value=similar.Plan(sets=[expanded])):
            similar.rebuild([])
        current.refresh_from_db();self.assertTrue(current.aktiv)
        self.assertEqual(SimilarGroup.objects.filter(aktiv=True).count(),1)
        old.refresh_from_db();self.assertEqual(old.question_order,ids);self.assertEqual(old.similar_group_id,group.pk)

    def test_new_mixed_set_is_visible_to_students(self):
        self.assertEqual(self.post(new_set_name='Yangi aralash',new_set_name_ru='Новый набор').status_code,302)
        group=SimilarGroup.objects.get(aktiv=True,is_manual=True)
        self.assertEqual(group.collection,'mixed')
        self.client.force_login(self.student)
        response=self.client.get('/uz/ohshash_savollar/')
        self.assertContains(response,'Yangi aralash')
        self.assertEqual(self.client.get(reverse('start_ohshash_test',args=[group.pk])).status_code,302)

    def test_empty_destinations_are_rejected(self):
        self.assertEqual(self.post(use_in_bilet='',use_in_topics='',use_in_mixed='',auto_similar='').status_code,200)
        self.assertFalse(Question.objects.filter(matn_uzb='New question').exists())
