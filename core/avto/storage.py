import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage


class VersionedStaticFilesStorage(StaticFilesStorage):
    """Appends the file's modification time to every static URL.

    The dev server sends no cache headers, so a browser can keep an old copy of a changed
    CSS/JS file and mix it with a newer page. A new URL forces a fresh download.
    """

    def url(self, name):
        url = super().url(name)
        path = finders.find(name)
        if isinstance(path, str) and os.path.isfile(path):
            return f"{url}?v={int(os.path.getmtime(path))}"
        return url


class PrivateStorage(FileSystemStorage):
    """Voice explanations live outside MEDIA_ROOT: they have no public URL, only the gated view serves them."""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(settings.PRIVATE_MEDIA_ROOT)


def private_storage():
    return PrivateStorage()
