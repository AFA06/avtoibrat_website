from uuid import uuid4
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from .admin_access import school_admin_required
from .student_views import _page
from .lecture_models import LectureTopic, LecturePage
from .lecture_forms import TopicForm, PageForm, ImportForm
from .lecture_import import import_pages


def lang_checked(lang):
    if lang not in ('uz', 'ru'):
        raise Http404
    return lang


def destination(topic, lang):
    return reverse('lectures:topic', args=[topic.pk, lang])


def bump(topic):
    LectureTopic.objects.filter(pk=topic.pk).update(revision=F('revision')+1)


@school_admin_required
def overview(request):
    trash = request.GET.get('trash') == '1'
    topics = LectureTopic.objects.filter(deleted=trash).annotate(
        uz_count=Count('pages', filter=Q(pages__language='uz', pages__deleted=False)),
        ru_count=Count('pages', filter=Q(pages__language='ru', pages__deleted=False)))
    return render(request, 'admin/lectures/list.html', _page(request, 'Konspektlar', topics=topics, trash=trash))


@school_admin_required
def topic_form(request, pk=None):
    topic = get_object_or_404(LectureTopic, pk=pk, deleted=False) if pk else None
    form = TopicForm(request.POST if request.method == 'POST' else None, instance=topic)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            if not saved.pk:
                saved.slug = 'mavzu-' + uuid4().hex[:16]
                saved.order = (LectureTopic.objects.aggregate(n=Max('order'))['n'] or 0)+1
            else:
                saved.revision = LectureTopic.objects.select_for_update().get(pk=saved.pk).revision+1
            saved.save()
        messages.success(request, 'Mavzu saqlandi. Endi har bir til uchun sahifalarni qo‘shing.')
        return redirect(destination(saved, 'uz'))
    return render(request, 'admin/lectures/form.html', _page(request, 'Mavzuni tahrirlash' if topic else 'Yangi mavzu', form=form, back=destination(topic, 'uz') if topic else reverse('lectures:list'), help='Ruscha sahifalar uchun ruscha mavzu nomini ham kiriting. Yangi mavzu dastlab yashirin.'))


@school_admin_required
def detail(request, pk, lang):
    lang_checked(lang)
    topic = get_object_or_404(LectureTopic, pk=pk, deleted=False)
    trash = request.GET.get('trash') == '1'
    pages = topic.pages.filter(language=lang, deleted=trash)
    query = request.GET.get('q', '').strip()
    if query:
        pages = pages.filter(Q(title__icontains=query) | Q(text__icontains=query))
    return render(request, 'admin/lectures/topic.html', _page(request, topic.title, topic=topic, pages=pages, lang=lang, trash=trash, query=query))


@school_admin_required
def page_form(request, pk, lang, page_id=None):
    lang_checked(lang)
    topic = get_object_or_404(LectureTopic, pk=pk, deleted=False)
    page = get_object_or_404(LecturePage, pk=page_id, topic=topic, language=lang, deleted=False) if page_id else LecturePage(topic=topic, language=lang)
    form = PageForm(request.POST if request.method == 'POST' else None, request.FILES or None, instance=page)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            LectureTopic.objects.select_for_update().get(pk=topic.pk)
            saved = form.save(commit=False)
            if not saved.pk:
                saved.order = (topic.pages.filter(language=lang).aggregate(n=Max('order'))['n'] or 0)+1
            if form.cleaned_data['remove_video']:
                saved.video = ''; saved.source_video = ''
            saved.save(); bump(topic)
        messages.success(request, 'Sahifa saqlandi.')
        if 'another' in request.POST:
            return redirect('lectures:page_new', pk=pk, lang=lang)
        return redirect(destination(topic, lang))
    return render(request, 'admin/lectures/form.html', _page(request, 'Sahifani tahrirlash' if page.pk else 'Yangi sahifa', form=form, current_page=page, back=destination(topic, lang), another=True, help='Tanlangan til: '+('O‘zbekcha' if lang == 'uz' else 'Русский')+'. Yangi rasm tanlamasangiz, mavjud rasm saqlanadi. Matnni o‘zgartirish rasm ichidagi yozuvni o‘zgartirmaydi; slayd yozuvi uchun rasmni ham almashtiring.'))


@school_admin_required
def upload(request, pk, lang):
    lang_checked(lang)
    topic = get_object_or_404(LectureTopic, pk=pk, deleted=False)
    form = ImportForm(request.POST if request.method == 'POST' else None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            count = import_pages(topic, lang, form.cleaned_data['files'])
        except (ValueError, RuntimeError, OSError) as error:
            form.add_error('files', 'Faylni o‘qib bo‘lmadi. Parolsiz PDF yoki to‘g‘ri rasm tanlang. '+str(error)[:160])
        else:
            messages.success(request, f'{count} ta sahifa yashirin holatda qo‘shildi. Tekshirib, keraklilarini belgilang va «Ko‘rsatish» tugmasini bosing.')
            return redirect(destination(topic, lang))
    return render(request, 'admin/lectures/form.html', _page(request, 'Sahifalarni birga yuklash', form=form, back=destination(topic, lang), help='1. PowerPoint’da «Save As / Сохранить как → PDF» ni tanlang. 2. Shu tilning PDF faylini yoki bir nechta rasmini yuklang. 3. Natijani tekshirib, talabalarga ko‘rsating. Eski sahifalar saqlanadi; yangilari oxiriga qo‘shiladi. Rasmlar tanlangan ketma-ketlikda qo‘shiladi.'))


@school_admin_required
@require_POST
def topic_action(request, pk, action):
    if action not in ('delete', 'restore', 'publish', 'hide', 'up', 'down'):
        raise Http404
    with transaction.atomic():
        topics = list(LectureTopic.objects.select_for_update().order_by('order', 'pk'))
        topic = next((t for t in topics if t.pk == pk), None)
        if not topic:
            raise Http404
        if action in ('up', 'down'):
            active = [t for t in topics if not t.deleted]
            if topic not in active:
                raise Http404
            index = active.index(topic); target = index+(-1 if action == 'up' else 1)
            if 0 <= target < len(active):
                active[index], active[target] = active[target], active[index]
                for order, item in enumerate(active):
                    LectureTopic.objects.filter(pk=item.pk).update(order=order)
        else:
            field = 'deleted' if action in ('delete', 'restore') else 'published'
            LectureTopic.objects.filter(pk=pk).update(**{field: action in ('delete', 'publish')}, revision=F('revision')+1)
    messages.success(request, 'O‘zgarish saqlandi. O‘chirilgan mavzuni savatchadan tiklash mumkin.')
    return redirect('lectures:list')


@school_admin_required
@require_POST
def page_action(request, pk, lang, action):
    lang_checked(lang)
    if action not in ('delete', 'restore', 'publish', 'hide', 'up', 'down'):
        raise Http404
    ids = request.POST.getlist('pages')
    if not ids or len(ids) > 200 or any(not value.isdigit() for value in ids):
        messages.error(request, 'Avval kerakli sahifalarni belgilang.')
        return redirect('lectures:topic', pk=pk, lang=lang)
    with transaction.atomic():
        topic = get_object_or_404(LectureTopic.objects.select_for_update(), pk=pk, deleted=False)
        pages = topic.pages.filter(language=lang, pk__in=ids, deleted=action == 'restore')
        if action in ('up', 'down'):
            if len(ids) != 1:
                raise Http404
            page = get_object_or_404(pages)
            ordered = list(topic.pages.filter(language=lang, deleted=False))
            index = ordered.index(page); target = index+(-1 if action == 'up' else 1)
            if 0 <= target < len(ordered):
                ordered[index], ordered[target] = ordered[target], ordered[index]
                for order, item in enumerate(ordered):
                    topic.pages.filter(pk=item.pk).update(order=order)
        else:
            field = 'deleted' if action in ('delete', 'restore') else 'published'
            pages.update(**{field: action in ('delete', 'publish')})
        bump(topic)
    messages.success(request, 'Sahifalar yangilandi. O‘chirilgan sahifalarni savatchadan tiklash mumkin.')
    return redirect(destination(topic, lang))
