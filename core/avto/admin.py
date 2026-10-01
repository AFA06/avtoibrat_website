from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    TestCategory, TestType, Question, Answer, TestSession, UserAnswer, SavedQuestion,
    TeamMember, Story, ConsultRequest, Testimonial, FAQ, ContactMessage, ContactPerson,
    RoadSignCategory, RoadSign, PdfMaterial, Branch, StudyGroup
)

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4
    verbose_name = _("Javob")
    verbose_name_plural = _("Javoblar")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("matn", "kategoriya", "test_turi")
    list_filter = ("kategoriya", "test_turi")
    search_fields = ("matn_uzb", "matn_uz_kr", "matn_rus")
    inlines = [AnswerInline]

    fieldsets = (
        (_("Asosiy ma’lumotlar"), {"fields": ("test_turi", "kategoriya", "matn_uzb","matn_uz_kr", "matn_rus")}),
        (_("Media fayllar"), {"fields": ("rasm", "audio_uzb", "audio_rus", "video_url")}),
    )



@admin.register(TestCategory)
class TestCategoryAdmin(admin.ModelAdmin):
    list_display = ("nomi", "tartib", "aktiv", "show_in_shablon", "show_in_real",
                    "show_in_mavzu", "show_in_ohshash")
    list_editable = ("tartib", "aktiv", "show_in_shablon", "show_in_real",
                     "show_in_mavzu", "show_in_ohshash")
    search_fields = ("nomi",)
    fieldsets = (
        (None, {"fields": ("nomi", "tavsif", "tartib", "aktiv")}),
        (_("Ko‘rinish"), {"fields": ("show_in_shablon", "show_in_real", "show_in_mavzu", "show_in_ohshash")}),
        (_("Parametrlar"), {"fields": ("question_count", "duration_minutes")}),
    )


@admin.register(TestType)
class TestTypeAdmin(admin.ModelAdmin):
    list_display = ("nomi", "vaqt_daqiqa", "savollar_soni")
    search_fields = ("nomi",)


@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "test_kind", "source", "started_at", "finished_at")
    list_filter = ("test_kind", "source")
    search_fields = ("user__username", "category__nomi")
    filter_horizontal = ("questions",)


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ("session", "question", "selected_answer", "is_correct")
    list_filter = ("is_correct",)
    search_fields = ("question__matn", "selected_answer__matn")


@admin.register(SavedQuestion)
class SavedQuestionAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "question__matn")

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "telegram", "instagram", "created_at")
    search_fields = ("full_name", "position")


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("id", "video", "is_active", "created_at")
    list_editable = ("is_active",)


@admin.register(ConsultRequest)
class ConsultRequestAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "created_at")
    search_fields = ("first_name", "last_name", "phone")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("full_name", "location", "title", "rating", "created_at")
    search_fields = ("full_name", "title")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "is_active", "order")
    list_editable = ("is_active", "order")
    search_fields = ("question",)
    ordering = ("order",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "subject", "created_at")
    search_fields = ("name", "phone", "subject")


@admin.register(ContactPerson)
class ContactPersonAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "city", "phone", "telegram", "is_active")
    list_editable = ("is_active",)
    search_fields = ("full_name", "position", "city")


@admin.register(RoadSignCategory)
class RoadSignCategoryAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "slug")
    list_display_links = ("title",)
    prepopulated_fields = {"slug": ("title",)}


@admin.register(RoadSign)
class RoadSignAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "category", "order")
    list_display_links = ("number", "title")
    list_filter = ("category",)
    search_fields = ("number", "title", "description")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(PdfMaterial)
class PdfMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "file", "created_at")
    search_fields = ("title",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("school_name", "name")
    search_fields = ("school_name", "name")


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "branch", "teacher")
    list_filter = ("category", "branch")
    search_fields = ("name", "teacher__username", "teacher__first_name", "teacher__last_name")
