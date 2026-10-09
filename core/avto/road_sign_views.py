"""Admin panel: «Belgilar» — teachers add road-sign categories and signs (/admin/road-signs/)."""
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import RoadSign, RoadSignCategory
from .road_signs import next_order, ordered_categories, sorted_signs, unique_slug
from .student_views import _page

IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
MAX_IMAGE_MB = 5


class SignImageField(forms.FileField):
    """Like ImageField but also accepts SVG, the usual format for road-sign artwork."""
    widget = forms.FileInput(attrs={"accept": ",".join(IMAGE_TYPES), "data-image-input": ""})

    def clean(self, data, initial=None):
        image = super().clean(data, initial)
        if image and hasattr(image, "size"):
            if not image.name.lower().endswith(IMAGE_TYPES):
                raise forms.ValidationError("Rasm PNG, JPG, GIF, WEBP yoki SVG formatida bo‘lishi kerak.")
            if image.size > MAX_IMAGE_MB * 1024 * 1024:
                raise forms.ValidationError(f"Rasm hajmi {MAX_IMAGE_MB} MB dan oshmasligi kerak.")
        return image


class CategoryForm(forms.ModelForm):
    image = SignImageField(label="Bo‘lim rasmi", required=False,
                           help_text="Ixtiyoriy. Bo‘sh qoldirilsa, birinchi belgi rasmi ishlatiladi.")

    class Meta:
        model = RoadSignCategory
        fields = ("title", "image")
        labels = {"title": "Bo‘lim nomi"}
        widgets = {"title": forms.TextInput(attrs={"placeholder": "Masalan: Taqiqlovchi belgilar"})}


class SignForm(forms.ModelForm):
    image = SignImageField(label="Belgi rasmi")

    class Meta:
        model = RoadSign
        fields = ("category", "number", "title", "description", "image")
        labels = {"category": "Bo‘lim", "number": "Raqami", "title": "Nomi", "description": "Tavsif"}
        help_texts = {"number": "Masalan: 3.1 yoki 1.4.2. Belgilar shu raqam bo‘yicha tartiblanadi."}
        widgets = {
            "number": forms.TextInput(attrs={"placeholder": "3.1"}),
            "title": forms.TextInput(attrs={"placeholder": "Masalan: Kirish taqiqlangan"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Belgi nimani anglatishi va haydovchi nima qilishi kerak"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ordered_categories()
        self.fields["category"].empty_label = None
        if self.instance.pk:
            self.fields["image"].required = False
            self.fields["image"].help_text = "Yangi rasm tanlamasangiz, hozirgisi qoladi."

    def clean_number(self):
        return self.cleaned_data["number"].strip()


@staff_member_required
def overview(request):
    categories = ordered_categories().annotate(sign_count=Count("signs"))
    return render(request, "admin/road_signs/list.html", _page(
        request, "Belgilar", categories=categories,
        sign_total=RoadSign.objects.count(),
    ))


@staff_member_required
def category_detail(request, pk):
    category = get_object_or_404(RoadSignCategory, pk=pk)
    return render(request, "admin/road_signs/category.html", _page(
        request, category.title, category=category, signs=sorted_signs(category),
    ))


@staff_member_required
def category_form(request, pk=None):
    category = get_object_or_404(RoadSignCategory, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, request.FILES or None, instance=category)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        if not saved.pk:
            saved.slug = unique_slug(RoadSignCategory, saved.title, "bolim")
            saved.order = next_order(RoadSignCategory)
        saved.save()
        messages.success(request, f"«{saved.title}» bo‘limi saqlandi.")
        return redirect("signs:category", pk=saved.pk)
    return render(request, "admin/road_signs/category_form.html", _page(
        request, category.title if category else "Yangi bo‘lim", form=form, category=category,
    ))


@staff_member_required
@require_POST
def category_move(request, pk, direction):
    """Swap this category with its neighbour so the teacher controls the order students see."""
    if direction not in ("up", "down"):
        raise Http404
    get_object_or_404(RoadSignCategory, pk=pk)
    categories = list(ordered_categories())
    index = next(i for i, c in enumerate(categories) if c.pk == pk)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(categories):
        categories[index], categories[target] = categories[target], categories[index]
        for position, category in enumerate(categories, start=1):
            if category.order != position:
                RoadSignCategory.objects.filter(pk=category.pk).update(order=position)
    return redirect("signs:list")


@staff_member_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(RoadSignCategory, pk=pk)
    title, count = category.title, category.signs.count()
    category.delete()
    messages.success(request, f"«{title}» bo‘limi va undagi {count} ta belgi o‘chirildi.")
    return redirect("signs:list")


@staff_member_required
def sign_form(request, pk=None):
    sign = get_object_or_404(RoadSign.objects.select_related("category"), pk=pk) if pk else None
    initial = {"category": request.GET.get("category")} if not sign else None
    form = SignForm(request.POST or None, request.FILES or None, instance=sign, initial=initial)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        if not saved.pk:
            saved.slug = unique_slug(RoadSign, f"{saved.number} {saved.title}")
            saved.order = next_order(RoadSign, category=saved.category)
        saved.save()
        messages.success(request, f"«{saved.full_title}» belgisi saqlandi.")
        if "add_another" in request.POST:
            return redirect(f"{reverse('signs:sign_create')}?category={saved.category_id}")
        return redirect("signs:category", pk=saved.category_id)
    back = sign.category if sign else RoadSignCategory.objects.filter(pk=request.GET.get("category") or 0).first()
    return render(request, "admin/road_signs/sign_form.html", _page(
        request, f"{sign.full_title}" if sign else "Yangi belgi", form=form, sign=sign, back=back,
    ))


@staff_member_required
@require_POST
def sign_delete(request, pk):
    sign = get_object_or_404(RoadSign, pk=pk)
    category_id, title = sign.category_id, sign.full_title
    sign.delete()
    messages.success(request, f"«{title}» belgisi o‘chirildi.")
    return redirect("signs:category", pk=category_id)
