from io import BytesIO
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from PIL import Image
from .lecture_models import LectureTopic, LecturePage, LectureUpload
from .lecture_import import import_pages
from .lectures import topics_for


def picture(name='page.png'):
    data=BytesIO(); Image.new('RGB',(80,60),'green').save(data,'PNG')
    return SimpleUploadedFile(name,data.getvalue(),content_type='image/png')


class LectureManagementTests(TestCase):
    def setUp(self):
        self.addCleanup(translation.activate,translation.get_language())
        User=get_user_model()
        self.admin=User.objects.create_user(username='admin-lectures',is_staff=True,is_superuser=True,unlimited=True)
        self.teacher=User.objects.create_user(username='teacher-lectures',is_staff=True,unlimited=True)
        self.topic=LectureTopic.objects.create(title='New topic',title_ru='Новая тема',slug='new-topic')
        self.client.force_login(self.admin)

    def url(self,name,*args):
        return reverse('lectures:'+name,args=args)

    def test_access_and_read_only_get(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url('list')).status_code,403)
        self.assertEqual(self.client.post(self.url('action',self.topic.pk,'delete')).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('action',self.topic.pk,'delete')).status_code,405)

    def test_forms_create_replace_and_durable_files(self):
        for name,args in [('list',[]),('new',[]),('edit',[self.topic.pk]),('topic',[self.topic.pk,'uz']),('upload',[self.topic.pk,'ru']),('page_new',[self.topic.pk,'uz'])]:
            self.assertEqual(self.client.get(self.url(name,*args)).status_code,200)
        self.client.post(self.url('new'),{'title':'Another'})
        self.assertTrue(LectureTopic.objects.filter(title='Another',published=False).exists())
        response=self.client.post(self.url('page_new',self.topic.pk,'uz'),{'title':'First','text':'Rule','kind':'rule','image':picture(),'published':'on'})
        self.assertEqual(response.status_code,302)
        page=self.topic.pages.get(); old=page.image.name
        self.assertEqual(self.client.get(page.image.url).status_code,200)
        self.assertEqual(self.client.get(page.image.url,HTTP_RANGE='bytes=0-9').status_code,206)
        self.client.post(self.url('page_edit',self.topic.pk,'uz',page.pk),{'title':'Updated','kind':'example','image':picture('new.png')})
        page.refresh_from_db();self.assertNotEqual(page.image.name,old)
        self.assertTrue(LectureUpload.objects.filter(name=old).exists())

    def test_publish_restore_and_language_isolation(self):
        import_pages(self.topic,'uz',[picture()]);import_pages(self.topic,'ru',[picture()])
        uz=self.topic.pages.get(language='uz');ru=self.topic.pages.get(language='ru')
        self.client.post(self.url('action',self.topic.pk,'publish'))
        visible=lambda:any(t['slug']==self.topic.slug for t in topics_for('uz'))
        self.assertFalse(visible())
        self.client.post(self.url('page_action',self.topic.pk,'uz','publish'),{'pages':[uz.pk,ru.pk]})
        ru.refresh_from_db();self.assertFalse(ru.published);self.assertTrue(visible())
        self.assertContains(self.client.get("/uz/konspekt/new-topic/"), "/lecture-assets/"+uz.image.name)
        for action,expected in [('delete',False),('restore',True),('hide',False),('publish',True)]:
            self.client.post(self.url('page_action',self.topic.pk,'uz',action),{'pages':[uz.pk]});self.assertEqual(visible(),expected)
        self.client.post(self.url('action',self.topic.pk,'delete'));self.assertFalse(visible())
        self.client.post(self.url('action',self.topic.pk,'restore'));self.assertTrue(visible())

    def test_order_and_cross_topic_safety(self):
        import_pages(self.topic,'uz',[picture('one.png'),picture('two.png')])
        a,b=list(self.topic.pages.all());version=LectureTopic.objects.get(pk=self.topic.pk).revision
        self.client.post(self.url('page_action',self.topic.pk,'uz','up'),{'pages':[b.pk]})
        self.assertEqual(list(self.topic.pages.values_list('pk',flat=True)),[b.pk,a.pk])
        self.assertGreater(LectureTopic.objects.get(pk=self.topic.pk).revision,version)
        foreign=LecturePage.objects.exclude(topic=self.topic).first()
        self.client.post(self.url('page_action',self.topic.pk,'uz','delete'),{'pages':[foreign.pk]})
        foreign.refresh_from_db();self.assertFalse(foreign.deleted)

    def test_pdf_and_failed_import_atomicity(self):
        import pymupdf
        doc=pymupdf.open();doc.new_page().insert_text((50,50),'A test rule');doc.new_page()
        pdf=SimpleUploadedFile('lesson.pdf',doc.tobytes(),content_type='application/pdf');doc.close()
        self.assertEqual(import_pages(self.topic,'ru',[pdf]),2)
        self.assertFalse(self.topic.pages.filter(published=True).exists())
        self.assertIn('A test rule',self.topic.pages.first().text)
        before=LectureUpload.objects.count()
        with self.assertRaises(OSError):import_pages(self.topic,'uz',[picture(),SimpleUploadedFile('bad.png',b'bad')])
        self.assertEqual(LectureUpload.objects.count(),before)
        self.assertFalse(self.topic.pages.filter(language='uz').exists())
        response=self.client.post(self.url('upload',self.topic.pk,'uz'),{'files':SimpleUploadedFile('bad.pdf',b'bad')})
        self.assertEqual(response.status_code,200)

    def test_originals_and_empty_page_validation(self):
        self.assertEqual(LecturePage.objects.exclude(topic=self.topic).count(),1049)
        self.assertEqual(len(topics_for('ru')),7)
        response=self.client.post(self.url('page_new',self.topic.pk,'uz'),{'title':'Missing image','kind':'rule','published':'on'})
        self.assertEqual(response.status_code,200);self.assertFalse(self.topic.pages.exists())
