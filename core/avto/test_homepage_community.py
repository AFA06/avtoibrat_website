from datetime import date

from django.test import TestCase

from .models import GraduateAchievement, TeamMember, Testimonial


class HomepageCommunityTests(TestCase):
    def test_all_sections_and_original_car_are_present_without_content(self):
        response = self.client.get('/uz/')
        self.assertEqual(response.status_code, 200)
        for section in ('roadmap', 'teachers', 'instructors', 'graduates', 'reviews'):
            self.assertContains(response, f'id="{section}"')
        self.assertContains(response, 'site/drive/gentra.glb')
        self.assertContains(response, 'site/drive/experience.js')
        self.assertNotContains(response, 'class="voice-rating"')

    def test_only_explicitly_published_graduate_stories_are_public(self):
        fields = dict(image='graduates/example.jpg', category='B',
                      achievement='Kursni tugatdi', graduated_on=date(2026, 11, 1))
        GraduateAchievement.objects.create(full_name='Private student', **fields)
        GraduateAchievement.objects.create(full_name='Published graduate', is_published=True, **fields)
        response = self.client.get('/uz/')
        self.assertContains(response, 'Published graduate')
        self.assertNotContains(response, 'Private student')
        self.assertContains(response, 'Kursni tugatdi')

    def test_staff_are_grouped_by_their_actual_role(self):
        TeamMember.objects.create(full_name='Theory teacher', position='Theory', role='teacher')
        TeamMember.objects.create(full_name='Driving instructor', position='Practice', role='instructor')
        response = self.client.get('/uz/')
        html = response.content.decode()
        teacher_html, instructor_html = html.split('id="instructors"', 1)
        self.assertIn('Theory teacher', teacher_html)
        self.assertNotIn('Driving instructor', teacher_html)
        self.assertIn('Driving instructor', instructor_html)
        self.assertNotIn('Theory teacher', instructor_html)

    def test_reviews_use_saved_text_and_rating(self):
        Testimonial.objects.create(full_name='Review author', location='Toshkent', title='My experience',
                                   text='An actual saved review', rating=4)
        response = self.client.get('/uz/')
        self.assertContains(response, 'An actual saved review')
        self.assertContains(response, '4 / 5')
        self.assertContains(response, 'Review author')

    def test_new_headings_are_translated(self):
        for lang, heading in (('ru', 'Стена достижений'), ('uz-kr', 'Ютуқлар девори')):
            self.assertContains(self.client.get(f'/{lang}/'), heading)

    def test_content_admin_pages_are_accessible_to_the_owner(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        owner = get_user_model().objects.create_superuser(username='content-owner', password='test-only')
        self.client.force_login(owner)
        for model in ('graduateachievement', 'teammember', 'testimonial'):
            response = self.client.get(reverse(f'admin:avto_{model}_changelist'))
            self.assertContains(response, 'Sayt kontenti')
            self.assertContains(response, 'Bitiruvchilar yutuqlari')
