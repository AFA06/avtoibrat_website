"""Editable lecture content; original assets remain available after replacement."""
from django.db import models
from .lecture_storage import LectureStorage


class LectureTopic(models.Model):
    slug = models.SlugField(unique=True, max_length=80)
    title = models.CharField('Mavzu nomi (o‘zbekcha)', max_length=200)
    title_kr = models.CharField('Mavzu nomi (kirill)', max_length=200, blank=True)
    title_ru = models.CharField('Mavzu nomi (ruscha)', max_length=200, blank=True)
    description = models.TextField('Qisqa tavsif (o‘zbekcha)', blank=True)
    description_kr = models.TextField('Qisqa tavsif (kirill)', blank=True)
    description_ru = models.TextField('Qisqa tavsif (ruscha)', blank=True)
    published = models.BooleanField('Talabalarga ko‘rsatish', default=False)
    deleted = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ('order', 'pk')

    def __str__(self):
        return self.title


class LecturePage(models.Model):
    topic = models.ForeignKey(LectureTopic, on_delete=models.CASCADE, related_name='pages')
    language = models.CharField('Til', max_length=2, choices=(('uz', 'O‘zbekcha'), ('ru', 'Русский')))
    title = models.CharField('Sahifa sarlavhasi', max_length=250, blank=True)
    text = models.TextField('Tushuntirish matni', blank=True)
    kind = models.CharField('Sahifa turi', max_length=10, choices=(('rule', 'Qoida'), ('example', 'Misol / savol')), default='rule')
    is_cover = models.BooleanField('Muqova sahifasi', default=False)
    image = models.ImageField('Sahifa rasmi', upload_to='lectures/images/', storage=LectureStorage(), blank=True)
    video = models.FileField('Video (ixtiyoriy)', upload_to='lectures/videos/', storage=LectureStorage(), blank=True)
    source_image = models.CharField(max_length=200, blank=True)
    source_thumbnail = models.CharField(max_length=200, blank=True)
    source_video = models.CharField(max_length=200, blank=True)
    published = models.BooleanField('Talabalarga ko‘rsatish', default=False)
    deleted = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')
        indexes = [models.Index(fields=['topic', 'language', 'order'])]

    @property
    def image_name(self):
        return 'media:' + self.image.name if self.image else self.source_image

    @property
    def thumbnail_name(self):
        return self.image_name if self.image else (self.source_thumbnail or self.source_image)

    @property
    def video_name(self):
        return 'media:' + self.video.name if self.video else self.source_video

    def __str__(self):
        return self.title or f'Sahifa {self.pk}'


class LectureUpload(models.Model):
    name = models.CharField(max_length=80, unique=True)
    data = models.BinaryField()
