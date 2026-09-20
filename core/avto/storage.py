import os

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
