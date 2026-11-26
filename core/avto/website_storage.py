"""Public website pictures stored with the database, with legacy media compatibility."""
from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from PIL import Image, ImageOps


def picture_bytes(file, crop=None):
    if file.size > 5 * 1024 * 1024:
        raise ValueError("Rasm hajmi 5 MB dan oshmasin.")
    file.seek(0)
    with Image.open(file) as source:
        if source.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("JPG, PNG yoki WEBP rasm tanlang.")
        if source.width * source.height > 25_000_000:
            raise ValueError("Rasm juda katta. 25 megapikseldan kichik rasm tanlang.")
        image = ImageOps.exif_transpose(source).convert("RGBA" if "A" in source.getbands() else "RGB")
        if crop:
            image = ImageOps.fit(image, crop, method=Image.Resampling.LANCZOS)
        else:
            image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, "WEBP", quality=88, method=3)
    return output.getvalue()


@deconstructible
class WebsiteStorage(Storage):
    prefix = "website/"

    def _save(self, name, content):
        from .models import WebsiteUpload
        data = picture_bytes(content)
        name = uuid4().hex + ".webp"
        WebsiteUpload.objects.create(name=name, data=data)
        return self.prefix + name

    def _open(self, name, mode="rb"):
        from .models import WebsiteUpload
        if not name.startswith(self.prefix):
            return FileSystemStorage().open(name, mode)
        return ContentFile(bytes(WebsiteUpload.objects.get(name=name[len(self.prefix):]).data), name=name)

    def exists(self, name):
        from .models import WebsiteUpload
        if not name.startswith(self.prefix):
            return FileSystemStorage().exists(name)
        return WebsiteUpload.objects.filter(name=name[len(self.prefix):]).exists()

    def url(self, name):
        return reverse("website_asset", args=[name[len(self.prefix):]]) if name.startswith(self.prefix) else FileSystemStorage().url(name)

    def size(self, name):
        with self.open(name) as file:
            return file.size

    def delete(self, name):
        # Keep replaced images recoverable and never delete a shared legacy file.
        pass
