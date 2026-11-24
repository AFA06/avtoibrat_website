"""Validate a complete upload before saving any pages; roll back files on failure."""
from io import BytesIO
from pathlib import Path
import warnings
from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from .lecture_storage import LectureStorage
from django.db import transaction
from django.db.models import Max, F
from .lecture_models import LectureTopic, LecturePage


def prepare(files):
    result = []
    for upload in files:
        if upload.name.lower().endswith('.pdf'):
            import pymupdf
            with pymupdf.open(stream=upload.read(), filetype='pdf') as doc:
                if doc.needs_pass or not 1 <= len(doc) <= 200:
                    raise ValueError('PDF parolsiz va 1–200 sahifadan iborat bo‘lishi kerak.')
                for index, page in enumerate(doc):
                    if page.rect.width <= 0 or page.rect.height <= 0:
                        raise ValueError("PDF sahifasining o‘lchami yaroqsiz.")
                    scale = min(1600 / max(page.rect.width, page.rect.height), 2)
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                    with Image.frombytes('RGB', (pix.width, pix.height), pix.samples) as image:
                        buf = BytesIO(); image.save(buf, 'WEBP', quality=85)
                    text = page.get_text().strip()
                    result.append((f'{Path(upload.name).stem} · {index+1}', text, buf.getvalue()))
        else:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(upload) as original:
                    if original.format not in ('PNG', 'JPEG', 'WEBP'):
                        raise ValueError('Faqat PNG, JPG yoki WEBP rasmlardan foydalaning.')
                    if original.width * original.height > 25_000_000:
                        raise ValueError('Rasm 25 megapikseldan oshmasligi kerak.')
                    image = ImageOps.exif_transpose(original).convert('RGB')
                    image.thumbnail((1600, 1600))
                    buf = BytesIO(); image.save(buf, 'WEBP', quality=85)
            result.append((Path(upload.name).stem, '', buf.getvalue()))
        if len(result) > 200 or sum(len(item[2]) for item in result) > 60 * 1024 * 1024:
            raise ValueError('Bir yuklashda 200 sahifagacha qo‘shish mumkin. Faylni kichikroq qismlarga ajrating.')
    return result


def import_pages(topic, language, files):
    prepared = prepare(files)
    saved = []
    try:
        with transaction.atomic():
            LectureTopic.objects.select_for_update().get(pk=topic.pk)
            order = LecturePage.objects.filter(topic=topic, language=language).aggregate(n=Max('order'))['n'] or 0
            for offset, (title, text, content) in enumerate(prepared, 1):
                page = LecturePage(topic=topic, language=language, title=title[:250], text=text, order=order+offset)
                page.image.save('page.webp', ContentFile(content), save=False)
                saved.append(page.image.name); page.save()
            LectureTopic.objects.filter(pk=topic.pk).update(revision=F('revision')+1)
    except Exception:
        for name in saved:
            LectureStorage().delete(name)
        raise
    return len(prepared)
