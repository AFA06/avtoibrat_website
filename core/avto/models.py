import hashlib
import re
from django.utils.translation import gettext_lazy as _
from django.utils.translation import get_language

from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

from pydub import AudioSegment
from PIL import Image


def validate_image_size(image):
    img = Image.open(image)
    w, h = img.size
    if w != 360 or h != 300:
        raise ValidationError("Rasm o‘lchami aniq 360x300 bo‘lishi kerak!")


def validate_question_image(image):
    img = Image.open(image)
    w, h = img.size
    if w != 945 or h != 530:
        raise ValidationError("Rasm o‘lchami aniq 945x530 bo‘lishi kerak!")


def validate_audio_duration(audio):
    if audio.size > 5 * 1024 * 1024:  # 5MB
        raise ValidationError("Audio hajmi 5MB dan oshmasligi kerak")


def video_embed_url(self):
    if "youtube.com/watch?v=" in self.video_url:
        video_id = self.video_url.split("v=")[1].split("&")[0]
        return f"https://www.youtube.com/embed/{video_id}"
    return self.video_url


class TeamMember(models.Model):
    full_name = models.CharField(max_length=150)
    position = models.CharField(max_length=255)
    image = models.ImageField(
        upload_to="team/",
        validators=[validate_image_size]
    )
    telegram = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Story(models.Model):
    video = models.FileField(upload_to="stories/")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Story #{self.id}"


class ConsultRequest(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Testimonial(models.Model):
    full_name = models.CharField(max_length=150)
    location = models.CharField(max_length=150)
    title = models.CharField(max_length=255)
    text = models.TextField()
    image = models.ImageField(upload_to="testimonials/")
    rating = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)  # ✅ BOR

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.question


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    subject = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.phone}"

class ContactPerson(models.Model):
    full_name = models.CharField(
        max_length=255,
        verbose_name="To‘liq ism"
    )
    position = models.CharField(
        max_length=255,
        verbose_name="Lavozimi"
    )
    city = models.CharField(
        max_length=100,
        verbose_name="Shahar"
    )
    phone = models.CharField(
        max_length=20,
        verbose_name="Telefon raqam"
    )
    telegram = models.URLField(
        blank=True,
        verbose_name="Telegram havola"
    )
    image = models.ImageField(
        upload_to="contacts/",
        blank=True,
        null=True
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Faolmi"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Bog‘lanish uchun shaxs"
        verbose_name_plural = "Bog‘lanish uchun"
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name


class RoadSignCategory(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    image = models.ImageField(upload_to="road_sign_categories/", blank=True, null=True)

    def __str__(self):
        return self.title


class RoadSign(models.Model):
    category = models.ForeignKey(
        RoadSignCategory,
        related_name="signs",
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to="road_signs/")
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.title


class PdfMaterial(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="pdfs/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

def get_device_id(request):
    raw = (
        request.META.get("HTTP_USER_AGENT", "") +
        request.META.get("REMOTE_ADDR", "")
    )
    return hashlib.sha256(raw.encode()).hexdigest()


UZ_COUNTRY_CODE = "998"
UZ_FULL_NUMBER_LENGTH = len(UZ_COUNTRY_CODE) + 9


def normalize_phone(value):
    """Digits only, without the +998 country code, so any typed format compares equal."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == UZ_FULL_NUMBER_LENGTH and digits.startswith(UZ_COUNTRY_CODE):
        digits = digits[len(UZ_COUNTRY_CODE):]
    return digits


class User(AbstractUser):
    GROUP_LANGUAGE_CHOICES = (
        ("uz", "Oʻzbek guruhi (lotin)"),
        ("uz-kr", "Ўзбек гуруҳи (кирилл)"),
        ("ru", "Русская группа"),
    )

    phone = models.CharField(max_length=20, blank=True)

    account_started_at = models.DateTimeField(null=True, blank=True)
    account_expires_at = models.DateTimeField(null=True, blank=True)
    unlimited = models.BooleanField(default=False)

    device_limit = models.PositiveSmallIntegerField(
        default=30,
        help_text="Nechta qurilmadan login qilish mumkin (1–30)"
    )

    group_language = models.CharField(
        max_length=10,
        choices=GROUP_LANGUAGE_CHOICES,
        default="uz",
        verbose_name="Guruh tili",
        help_text="Talaba savol va javoblarni shu tilda ko‘radi. Sayt interfeysi tilidan mustaqil."
    )

    def clean(self):
        super().clean()
        if not normalize_phone(self.phone):
            if not (self.is_staff or self.is_superuser):
                raise ValidationError({"phone": "Talaba uchun telefon raqami majburiy."})
            return

        target = normalize_phone(self.phone)
        other_phones = User.objects.exclude(pk=self.pk).exclude(phone="").values_list("phone", flat=True)
        if any(normalize_phone(phone) == target for phone in other_phones):
            raise ValidationError({"phone": "Bu telefon raqami boshqa foydalanuvchida mavjud."})

    def vaqt_boyicha_faolmi(self):
        if self.unlimited:
            return True
        if not self.account_started_at or not self.account_expires_at:
            return False
        now = timezone.now()
        return self.account_started_at <= now < self.account_expires_at

    def has_active_account(self):
        if self.is_superuser or self.unlimited:
            return True
        return self.vaqt_boyicha_faolmi()

    def sync_active_status(self):
        active = self.has_active_account()
        if self.is_active != active:
            self.is_active = active
            self.save(update_fields=["is_active"])


class UserDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices"
    )
    device_id = models.CharField(max_length=255)
    user_agent = models.TextField()
    ip_address = models.GenericIPAddressField()
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "device_id")

    def __str__(self):
        return f"{self.user.username} | {self.device_id}"



class TestCategory(models.Model):
    nomi = models.CharField(max_length=255)
    tavsif = models.TextField(blank=True)
    tartib = models.PositiveIntegerField(default=1)
    aktiv = models.BooleanField(default=True)

    show_in_shablon = models.BooleanField(default=False)
    show_in_real = models.BooleanField(default=False)
    show_in_mavzu = models.BooleanField(default=False)
    show_in_ohshash = models.BooleanField(default=False)

    question_count = models.PositiveIntegerField(default=20)
    duration_minutes = models.PositiveIntegerField(default=25)

    class Meta:
        ordering = ["tartib"]

    def __str__(self):
        return self.nomi


class TestType(models.Model):
    nomi = models.CharField(max_length=100)
    vaqt_daqiqa = models.PositiveIntegerField()
    savollar_soni = models.PositiveIntegerField()

    def __str__(self):
        return self.nomi




class Question(models.Model):
    test_turi = models.ForeignKey(TestType, on_delete=models.CASCADE)
    kategoriya = models.ForeignKey(TestCategory, on_delete=models.CASCADE)

    matn_uzb = models.TextField("Savol (O‘zbek)")
    matn_uz_kr = models.TextField("Savol (Крил)")
    matn_rus = models.TextField("Savol (Русский)")

    matn = models.TextField("Savol (legacy)", blank=True)

    rasm = models.ImageField(
        upload_to="questions/images/",
        blank=True,
        null=True,
        validators=[validate_question_image],
    )

    audio_uzb = models.FileField(
        upload_to="questions/audio/",
        blank=True,
        null=True,
        validators=[validate_audio_duration],
    )
    audio_rus = models.FileField(
        upload_to="questions/audio/",
        blank=True,
        null=True,
        validators=[validate_audio_duration],
    )

    video_url = models.URLField(blank=True, null=True)

    def get_text(self, lang=None):
        lang = lang or get_language()

        if lang in ("uz",):  # uz
            return self.matn_uzb

        elif lang in ("uz-kr",):  # uz-kr (krill)
            return self.matn_uz_kr

        elif lang in ("ru",):  # ru
            return self.matn_rus

        return self.matn_uzb

    def get_audio_file(self):
        lang = get_language()
        if lang in ("uz", "uz-kr"):
            return self.audio_uzb.url if self.audio_uzb else None
        elif lang == "ru":
            return self.audio_rus.url if self.audio_rus else None
        return None

    @property
    def video_embed_url(self):
        if not self.video_url:
            return ""
        return self.video_url.replace("watch?v=", "embed/")


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        related_name="javoblar",
        on_delete=models.CASCADE
    )

    matn_uzb = models.CharField(max_length=255)
    matn_uz_kr = models.CharField(max_length=255)
    matn_rus = models.CharField(max_length=255)

    togri = models.BooleanField(default=False)

    def get_text(self, lang=None):
        lang = lang or get_language()

        if lang in ("uz",):
            return self.matn_uzb

        elif lang in ("uz-kr",):
            return self.matn_uz_kr

        elif lang in ("ru",):
            return self.matn_rus

        return self.matn_uzb



class TestSession(models.Model):
    TEST_KIND = (
        ("shablon", "Shablon test"),
        ("real", "Real imtihon"),
    )

    SOURCE_KIND = (
        ("shablon", "Shablon"),
        ("mavzu", "Mavzulashtirilgan"),
        ("ohshash", "O‘xshash"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(TestCategory, on_delete=models.CASCADE)
    test_kind = models.CharField(max_length=20, choices=TEST_KIND)
    source = models.CharField(
        max_length=20,
        choices=SOURCE_KIND,
        default="shablon"
    )

    questions = models.ManyToManyField(Question, blank=True)
    question_order = models.JSONField(default=list, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} | {self.category} | {self.source}"




class UserAnswer(models.Model):
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.ForeignKey(Answer, on_delete=models.SET_NULL, null=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ("session", "question")




class SavedQuestion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_questions"
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "question")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.question.id}"

