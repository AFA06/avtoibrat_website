"""Lecture uploads live with the database, including on ephemeral Render disks."""
from uuid import uuid4
from pathlib import Path
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class LectureStorage(Storage):
    def _open(self, name, mode='rb'):
        from .lecture_models import LectureUpload
        return ContentFile(bytes(LectureUpload.objects.get(name=name).data), name=name)

    def _save(self, name, content):
        from .lecture_models import LectureUpload
        data = content.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise ValueError('Fayl juda katta.')
        name = uuid4().hex + Path(name).suffix.lower()
        LectureUpload.objects.create(name=name, data=data)
        return name

    def exists(self, name):
        from .lecture_models import LectureUpload
        return LectureUpload.objects.filter(name=name).exists()

    def size(self, name):
        with self.open(name) as file:
            return file.size

    def url(self, name):
        return reverse('lecture_asset', args=[name])

    def delete(self, name):
        # Replaced/deleted pages remain recoverable; never remove shared files.
        pass
