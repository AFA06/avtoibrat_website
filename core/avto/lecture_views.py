from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse

from .lectures import COPY, language, topics_for, asset_url


def _context(request):
    lang = language(request.LANGUAGE_CODE)
    return {"copy": COPY[lang], "lecture_language": lang, "storage_scope": f"{request.user.pk}:{'ru' if lang == 'ru' else 'uz'}"}


@login_required
def lecture_library(request):
    context = _context(request)
    topics = topics_for(context["lecture_language"])
    context["topics"] = topics
    context["total_slides"] = sum(t["count"] for t in topics)
    context["catalog"] = [{"slug": t["slug"], "title": t["title"], "start_page": t["start_page"], "revision": t["revision"], "url": reverse("lecture_reader", args=[t["slug"]]), "slides": [{"id": s["id"], "number": s["number"], "title": s["title"], "text": " ".join(s["paragraphs"]), "kind": s["kind"], "thumbnail": asset_url(s["thumbnail"])} for s in t["slides"]]} for t in topics]
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
                   deck={**topic, "slides": [{**s, "image": asset_url(s["image"]), "thumbnail": asset_url(s["thumbnail"]), "video": asset_url(s["video"]) if s.get("video") else None} for s in topic["slides"]]})
    return render(request, "dashboard/lecture_reader.html", context)


def lecture_asset(request, name):
    """Immutable, unguessable URLs, like the library's original static assets."""
    import re
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from .lecture_models import LectureUpload
    if not re.fullmatch(r'[a-f0-9]{32}\.(webp|png|jpg|jpeg|mp4)', name):
        raise Http404
    upload = get_object_or_404(LectureUpload, name=name)
    data = bytes(upload.data)
    content_type = 'video/mp4' if name.endswith('.mp4') else 'image/'+('jpeg' if name.endswith(('.jpg', '.jpeg')) else name.rsplit('.', 1)[1])
    status = 200
    headers = {}
    if request.headers.get('Range'):
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', request.headers['Range'])
        if not match or not any(match.groups()):
            return HttpResponse(status=416, headers={'Content-Range': f'bytes */{len(data)}'})
        start = int(match[1] or 0); end = min(int(match[2]) if match[2] else len(data)-1, len(data)-1)
        if not match[1]:
            start = max(0, len(data)-int(match[2])); end = len(data)-1
        if start > end or start >= len(data):
            return HttpResponse(status=416, headers={'Content-Range': f'bytes */{len(data)}'})
        headers['Content-Range'] = f'bytes {start}-{end}/{len(data)}'
        data = data[start:end+1]; status = 206
    response = HttpResponse(data, content_type=content_type, status=status, headers=headers)
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(len(data))
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
