"""Friendly, owner-only content editing. Public staff profiles are not login accounts."""
import re

from django import forms
from django.contrib import messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.templatetags.static import static
from django.views.decorators.http import require_POST, require_safe, require_http_methods

from .admin_access import school_admin_required
from .models import SchoolProfile, Course, TeamMember, ContactPerson, Testimonial, GraduateAchievement, FAQ, WebsiteUpload
from .public_site import normalize_phone
from .student_views import _page
from .website_storage import picture_bytes

SECTIONS = {
    'school': dict(model=SchoolProfile, title='Maktab ma’lumotlari', icon='school', description='Maktab nomi, telefon, manzil, ish vaqti va ijtimoiy tarmoqlar.', singleton=True, anchor='apply', fields=('brand_name','phone','address','hours','map_url','telegram','instagram','headline','intro','is_demo','headline_kr','headline_ru','intro_kr','intro_ru','address_kr','address_ru','hours_kr','hours_ru')),
    'images': dict(model=SchoolProfile, title='Sayt rasmlari', icon='images', description='Bosh sahifa, maktab, nazariya va amaliyot bo‘limlari rasmlarini almashtiring.', singleton=True, anchor='freedom', fields=('hero_background','about_image','teacher_image','instructor_image')),
    'founder': dict(model=SchoolProfile, title='Asoschi profili', icon='user-tie', description='Jamoa sahifasidagi asoschi ismi, rasmi va maktab ko‘rsatkichlari.', singleton=True, anchor=None, fields=('instructor_name','mentor_image','years_experience','graduates','pass_rate')),
    'courses': dict(model=Course, title='Kurslar va narxlar', icon='car', description='Kurs nomi, narxi, muddati va tarkibini yangilang.', anchor='courses', publish='is_active', search=('title','category'), fields=('category','title','price','duration','features','is_active','order','title_kr','title_ru','duration_kr','duration_ru','features_kr','features_ru')),
    'team': dict(model=TeamMember, title='O‘qituvchilar va instruktorlar', icon='users', description='Saytda ko‘rinadigan jamoa profillari. Bu yerda kabinet uchun hisob ochilmaydi.', anchor='teachers', publish='is_active', search=('full_name','position','location'), fields=('role','full_name','position','image','phone','location','telegram','instagram','is_active','order')),
    'contacts': dict(model=ContactPerson, title='Bog‘lanish uchun shaxslar', icon='phone', description='Aloqa sahifasidagi mas’ul shaxslar, telefonlar va shaharlar.', anchor=None, publish='is_active', search=('full_name','city','phone'), fields=('full_name','position','city','phone','telegram','image','is_active')),
    'reviews': dict(model=Testimonial, title='O‘quvchilar fikri', icon='comment', description='Haqiqiy fikrlar, mualliflar, suratlar va baholar.', anchor='reviews', search=('full_name','title'), fields=('full_name','location','title','text','rating','image')),
    'graduates': dict(model=GraduateAchievement, title='Bitiruvchilar yutuqlari', icon='award', description='Bitiruvchi roziligi bilan yutuqlar devoriga surat va natija qo‘shing.', anchor='graduates', publish='is_published', search=('full_name','achievement'), fields=('full_name','image','category','achievement','graduated_on','is_published','order')),
    'faq': dict(model=FAQ, title='Savol-javob', icon='question-circle', description='Tez-tez so‘raladigan savollar va javoblarni boshqaring.', anchor='faq', publish='is_active', search=('question','answer'), fields=('question','answer','is_active','order')),
}
LABELS = {'headline':'Bosh sahifadagi qisqa matn','headline_kr':'Qisqa matn (kirill)','headline_ru':'Qisqa matn (ruscha)','full_name':'Ism va familiya','position':'Lavozim / mutaxassislik','role':'Vazifasi','image':'Rasm','phone':'Telefon raqami','location':'Manzil / filial','city':'Shahar','title':'Sarlavha','text':'Fikr matni','rating':'Baho (1–5)','question':'Savol','answer':'Javob','order':'Saytdagi tartib','is_active':'Saytda ko‘rsatish','is_demo':'Saytda «namuna» belgisini ko‘rsatish','instructor_name':'Asoschi ismi','telegram':'Telegram havolasi','instagram':'Instagram havolasi'}
HELP = {'order':'Kichik raqam birinchi ko‘rinadi. Masalan: 1, 2, 3.', 'features':'Har bir qatorda bitta band yozing.', 'map_url':'Google Maps yoki boshqa xaritadagi joylashuv havolasini kiriting.', 'is_active':'Belgi olib tashlansa, yozuv saytdan yashiriladi.', 'is_published':'Faqat bitiruvchi roziligi olingach yoqing.', 'price':'Faqat so‘m miqdori. Masalan: 4500000.', 'telegram':'Masalan: https://t.me/avtoibrat', 'instagram':'Masalan: https://instagram.com/avtoibrat', 'is_demo':'Haqiqiy ma’lumotlar tayyor bo‘lsa, belgini olib tashlang.'}


class PictureWidget(forms.ClearableFileInput):
    template_name = 'admin/website/image_widget.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        defaults = {'hero_background':'site/atlas/summit.webp', 'about_image':'assets/images/resource/image-25.jpg', 'teacher_image':'assets/images/resource/image-21.jpg', 'instructor_image':'assets/images/resource/image-13.jpg', 'mentor_image':'site/demo/instructor.jpg'}
        context['widget']['fallback'] = static(defaults[name]) if name in defaults else None
        return context


class PictureField(forms.ImageField):
    widget = PictureWidget(attrs={'accept':'image/jpeg,image/png,image/webp', 'data-picture-input':''})

    def clean(self, value, initial=None):
        value = super().clean(value, initial)
        if not value or value is initial:
            return value
        try:
            data = picture_bytes(value, getattr(self, 'crop', None))
        except (ValueError, OSError) as error:
            raise forms.ValidationError(str(error))
        return SimpleUploadedFile('picture.webp', data, content_type='image/webp')


class ContentForm(forms.ModelForm):
    def __init__(self, *args, kind, **kwargs):
        self.kind = kind
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.label = LABELS.get(name, field.label)
            field.help_text = HELP.get(name, field.help_text)
            if name.endswith(('_kr','_ru')):
                field.help_text = 'Ixtiyoriy. Bo‘sh bo‘lsa, asosiy o‘zbekcha matn ko‘rinadi.'
            if isinstance(field, forms.ImageField):
                picture = PictureField(label=field.label, required=False)
                picture.crop = (360,300) if kind == 'team' else None
                picture.help_text = 'JPG, PNG yoki WEBP · 5 MB gacha. Rasm avtomatik moslanadi. Yangi rasm tanlamasangiz, hozirgisi qoladi.'
                self.fields[name] = picture
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 4
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'})
            if name == 'phone':
                field.widget.attrs.update(type='tel', placeholder='+998 90 123 45 67')
        if kind == 'courses':
            self.fields['title'].label = 'Kurs nomi'
            # These are the four categories supported by the cinematic collection.
            supported = ('A','B','BC','C')
            self.fields['category'].choices = [(c,c) for c in supported]
            if self.instance.pk and self.instance.category not in supported:
                self.fields['category'].choices += [(self.instance.category,self.instance.category)]

    def clean(self):
        data = super().clean()
        if data.get('phone'):
            phone = normalize_phone(data['phone'])
            if not phone:
                self.add_error('phone', 'Telefonni +998 va to‘liq raqam bilan kiriting.')
            else:
                data['phone'] = phone
        if self.kind == 'courses' and data.get('category'):
            if Course.objects.filter(category=data['category']).exclude(pk=self.instance.pk).exists():
                self.add_error('category', 'Bu toifa allaqachon bor. Mavjud kursni tahrirlang.')
        return data


def section(kind):
    if kind not in SECTIONS:
        raise Http404
    return SECTIONS[kind]


def public_url(spec):
    if spec is SECTIONS['contacts']:
        return reverse('contact')
    if spec is SECTIONS['faq']:
        return reverse('faq')
    if spec is SECTIONS['founder']:
        return reverse('team')
    return reverse('home') + ('#' + spec['anchor'] if spec.get('anchor') else '')


@school_admin_required
@require_safe
def overview(request):
    cards = []
    for kind, spec in SECTIONS.items():
        cards.append(dict(spec, kind=kind, count=None if spec.get('singleton') else spec['model'].objects.count(), url=reverse('website:edit', args=[kind]) if spec.get('singleton') else reverse('website:list', args=[kind])))
    return render(request, 'admin/website/overview.html', _page(request, 'Sayt kontenti', cards=cards, school=SchoolProfile.current()))


@school_admin_required
@require_safe
def listing(request, kind):
    spec = section(kind)
    if spec.get('singleton'):
        return redirect('website:edit', kind=kind)
    query = request.GET.get('q','').strip()[:150]
    objects = spec['model'].objects.all()
    if kind == 'team':
        objects = objects.order_by('order','pk')
    elif kind in ('reviews','contacts'):
        objects = objects.order_by('-pk')
    if query:
        condition = Q()
        for name in spec['search']:
            condition |= Q(**{name+'__icontains':query})
        objects = objects.filter(condition)
    rows = []
    page = Paginator(objects, 20).get_page(request.GET.get('page'))
    for obj in page:
        image = getattr(obj,'image',None)
        rows.append({'obj':obj, 'name':getattr(obj,'full_name',None) or getattr(obj,'question',None) or str(obj), 'subtitle':None if kind == 'courses' else (getattr(obj,'position',None) or getattr(obj,'achievement',None) or getattr(obj,'title',None)), 'image':image, 'published':getattr(obj,spec['publish']) if spec.get('publish') else True})
    return render(request, 'admin/website/list.html', _page(request, spec['title'], spec=spec, kind=kind, rows=rows, page=page, query=query, public_url=public_url(spec)))


@school_admin_required
@require_http_methods(['GET','POST'])
def edit(request, kind, pk=None):
    spec = section(kind)
    singleton = spec.get('singleton')
    if singleton:
        if pk is not None:
            raise Http404
        obj = SchoolProfile.current()
        if obj is None and kind != 'school':
            messages.info(request, 'Avval maktab ma’lumotlarini kiriting.')
            return redirect('website:edit', kind='school')
        obj = obj or SchoolProfile(pk=1)
    else:
        obj = get_object_or_404(spec['model'], pk=pk) if pk else None
    factory = forms.modelform_factory(spec['model'], form=ContentForm, fields=spec['fields'])
    form = factory(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, instance=obj, kind=kind)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, 'Saqlandi. O‘zgarishlar saytda ko‘rinadi.')
        return redirect('website:edit', kind=kind) if singleton else redirect('website:list', kind=kind)
    basic = [f for f in form if not f.name.endswith(('_kr','_ru'))]
    translations = [f for f in form if f.name.endswith(('_kr','_ru'))]
    return render(request, 'admin/website/form.html', _page(request, spec['title'], spec=spec, kind=kind, form=form, basic_fields=basic, translation_fields=translations, obj=obj, singleton=singleton, public_url=public_url(spec)))


@school_admin_required
@require_http_methods(['GET','POST'])
def delete(request, kind, pk):
    spec = section(kind)
    if spec.get('singleton'):
        raise Http404
    obj = get_object_or_404(spec['model'], pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Yozuv o‘chirildi.')
        return redirect('website:list', kind=kind)
    return render(request, 'admin/website/delete.html', _page(request, 'O‘chirishni tasdiqlang', kind=kind, obj=obj, spec=spec))


@school_admin_required
@require_POST
def toggle(request, kind, pk):
    spec = section(kind)
    field = spec.get('publish')
    if not field or spec.get('singleton'):
        raise Http404
    obj = get_object_or_404(spec['model'], pk=pk)
    setattr(obj,field,not getattr(obj,field))
    obj.save(update_fields=[field])
    messages.success(request, 'Saytdagi ko‘rinish yangilandi.')
    return redirect('website:list', kind=kind)


@require_safe
def asset(request, name):
    if not re.fullmatch(r'[a-f0-9]{32}\.webp', name):
        raise Http404
    upload = get_object_or_404(WebsiteUpload, name=name)
    response = HttpResponse(bytes(upload.data), content_type='image/webp')
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
