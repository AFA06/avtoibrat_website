from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse

from .lectures import COPY, language, topics_for


def _context(request):
    lang = language(request.LANGUAGE_CODE)
    return {"copy": COPY[lang], "lecture_language": lang, "storage_scope": f"{request.user.pk}:{'ru' if lang == 'ru' else 'uz'}"}


@login_required
def lecture_library(request):
    context = _context(request)
    topics = topics_for(context["lecture_language"])
    context["topics"] = topics
    context["total_slides"] = sum(t["count"] for t in topics)
    context["catalog"] = [{"slug": t["slug"], "title": t["title"], "start_page": t["start_page"], "url": reverse("lecture_reader", args=[t["slug"]]), "slides": [{"number": s["number"], "title": s["title"], "text": " ".join(s["paragraphs"]), "kind": s["kind"], "thumbnail": static(s["thumbnail"])} for s in t["slides"]]} for t in topics]
    return render(request, "dashboard/lecture_library.html", context)


@login_required
def lecture_reader(request, slug):
    context = _context(request)
    topic = next((t for t in topics_for(context["lecture_language"]) if t["slug"] == slug), None)
    if topic is None:
        raise Http404
    try:
        page = max(1, min(int(request.GET.get("slide", topic["start_page"])), topic["count"]))
    except (TypeError, ValueError):
        page = 1
    context.update(topic=topic, current=topic["slides"][page - 1], page=page,
                   deck={**topic, "slides": [{**s, "image": static(s["image"]), "thumbnail": static(s["thumbnail"]), "video": static(s["video"]) if s.get("video") else None} for s in topic["slides"]]})
    return render(request, "dashboard/lecture_reader.html", context)
