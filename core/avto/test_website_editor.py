from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import SchoolProfile, Course, TeamMember, Testimonial, WebsiteUpload


def photo(name='test.jpg', size=(900, 700)):
    output = BytesIO()
    Image.new('RGB', size, '#4b8271').save(output, 'JPEG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/jpeg')


class WebsiteEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(username='website-owner', password='local-test-only')
        cls.teacher = get_user_model().objects.create_user(username='website-teacher', is_staff=True, unlimited=True)

    def setUp(self):
        self.client.force_login(self.owner)

    def test_all_editor_pages_render_for_owner(self):
        from .website_views import SECTIONS
        self.assertContains(self.client.get(reverse('website:overview')), 'Veb-saytni boshqarish')
        for kind, spec in SECTIONS.items():
            url = reverse('website:edit' if spec.get('singleton') else 'website:create', args=[kind])
            self.assertContains(self.client.get(url), 'Saqlash')
            if not spec.get('singleton'):
                self.assertEqual(self.client.get(reverse('website:list',args=[kind])).status_code, 200)

    def test_non_owner_cannot_read_or_modify_content(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse('website:overview')).status_code, 403)
        self.assertEqual(self.client.post(reverse('website:create',args=['team']), {'full_name':'Should not exist'}).status_code,403)
        self.assertFalse(TeamMember.objects.filter(full_name='Should not exist').exists())
        self.client.logout()
        self.assertEqual(self.client.get(reverse('website:overview')).status_code,302)

    def test_edit_school_and_show_actual_public_values(self):
        response = self.client.post(reverse('website:edit',args=['school']), {'brand_name':'Test School','phone':'90 123 45 67','address':'Test address','hours':'09:00–18:00','headline':'Test headline','intro':'Test introduction'})
        self.assertEqual(response.status_code,302)
        school=SchoolProfile.current()
        self.assertEqual(school.phone,'+998901234567')
        for url in ['/uz/','/uz/contact/']:
            self.assertContains(self.client.get(url),'Test School')
            self.assertContains(self.client.get(url),'Test address')

    def test_photo_upload_is_cropped_and_survives_missing_media_directory(self):
        response=self.client.post(reverse('website:create',args=['team']), {'full_name':'Test instructor','role':'instructor','position':'Driving','phone':'90 123 45 67','image':photo(),'order':1,'is_active':'on'})
        self.assertEqual(response.status_code,302)
        member=TeamMember.objects.get(full_name='Test instructor')
        self.assertTrue(member.image.name.startswith('website/'))
        with TemporaryDirectory() as empty, override_settings(MEDIA_ROOT=empty):
            self.assertEqual(Image.open(member.image.open()).size,(360,300))
            response=self.client.get(member.image.url)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response['Content-Type'],'image/webp')
        self.assertContains(self.client.get('/uz/'),'Test instructor')
        member.is_active=False;member.save()
        self.assertNotContains(self.client.get('/uz/'),'Test instructor')
        self.assertNotContains(self.client.get('/uz/team/'),'Test instructor')

    def test_image_replacement_changes_url_and_no_file_keeps_image(self):
        member=TeamMember.objects.create(full_name='Photo person',role='teacher',position='Theory',image=photo())
        old=member.image.name
        data={'full_name':'Photo person','role':'teacher','position':'Theory','order':0,'is_active':'on'}
        self.client.post(reverse('website:update',args=['team',member.pk]),data)
        member.refresh_from_db();self.assertEqual(member.image.name,old)
        self.client.post(reverse('website:update',args=['team',member.pk]),{**data,'image':photo()})
        member.refresh_from_db();self.assertNotEqual(member.image.name,old)

    def test_duplicate_course_is_refused_and_existing_price_updates(self):
        course=Course.objects.filter(category='B').first()
        data={'category':'B','title':'Updated course','price':4800000,'duration':'3 months','features':'Theory\nPractice','order':0,'is_active':'on'}
        self.client.post(reverse('website:create',args=['courses']),data)
        self.assertEqual(Course.objects.filter(category='B').count(),1)
        self.assertEqual(self.client.post(reverse('website:update',args=['courses',course.pk]),data).status_code,302)
        self.assertContains(self.client.get('/uz/'),'Updated course')
        course.refresh_from_db();self.assertEqual(course.price,4800000)

    def test_delete_get_is_confirmation_and_post_deletes(self):
        item=Testimonial.objects.create(full_name='Test review',location='Tashkent',title='Good',text='Saved review',rating=5)
        url=reverse('website:delete',args=['reviews',item.pk])
        self.assertContains(self.client.get(url),'Ha, o‘chirish')
        self.assertTrue(Testimonial.objects.filter(pk=item.pk).exists())
        self.assertEqual(self.client.post(url).status_code,302)
        self.assertFalse(Testimonial.objects.filter(pk=item.pk).exists())

    def test_visibility_requires_post_and_changes_publication(self):
        member=TeamMember.objects.create(full_name='Visible teacher',role='teacher',position='Theory')
        url=reverse('website:toggle',args=['team',member.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.client.post(url);member.refresh_from_db();self.assertFalse(member.is_active)

    def test_invalid_phone_rating_and_non_image_are_not_saved(self):
        response=self.client.post(reverse('website:create',args=['reviews']),{'full_name':'Bad review','title':'Title','location':'City','text':'Text','rating':6})
        self.assertEqual(response.status_code,200);self.assertFalse(Testimonial.objects.filter(full_name='Bad review').exists())
        response=self.client.post(reverse('website:create',args=['team']),{'role':'teacher','full_name':'Bad photo','position':'Theory','order':0,'phone':'123','image':SimpleUploadedFile('bad.jpg',b'not an image')})
        self.assertEqual(response.status_code,200);self.assertFalse(TeamMember.objects.filter(full_name='Bad photo').exists())

    def test_optional_picture_can_be_removed(self):
        member=TeamMember.objects.create(full_name='Remove photo',role='teacher',position='Theory',image=photo())
        response=self.client.post(reverse('website:update',args=['team',member.pk]),{'role':'teacher','full_name':member.full_name,'position':'Theory','order':0,'image-clear':'on','is_active':'on'})
        self.assertEqual(response.status_code,302);member.refresh_from_db();self.assertFalse(member.image)

    def test_section_images_are_live_and_keep_the_opening_car(self):
        response=self.client.post(reverse('website:edit',args=['images']),{'hero_background':photo(),'about_image':photo()})
        self.assertEqual(response.status_code,302)
        school=SchoolProfile.current()
        response=self.client.get('/uz/')
        self.assertContains(response,school.hero_background.url)
        self.assertContains(response,school.about_image.url)
        self.assertContains(response,'site/drive/gentra.glb')

    def test_mutations_require_csrf(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(reverse('website:create',args=['team']),{'full_name':'CSRF blocked'}).status_code,403)
        self.assertFalse(TeamMember.objects.filter(full_name='CSRF blocked').exists())
