from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    TestCategory, TestType, Question, Answer, TestSession, UserAnswer, SavedQuestion,
    TeamMember, Story, ConsultRequest, Testimonial, FAQ, ContactMessage, ContactPerson, SchoolProfile, Course,
    RoadSignCategory, RoadSign, PdfMaterial, Branch, StudyGroup, Topic, TopicGroup, LoginLock
)
from django.db.models import Count

from .admin_access import groups_for, students_for

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4
    verbose_name = _("Javob")
    verbose_name_plural = _("Javoblar")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("matn_uzb", "kategoriya", "mavzu", "test_turi")
    list_filter = ("is_archived", "kategoriya", "mavzu__group", "mavzu", "test_turi")
    list_select_related = ("kategoriya", "mavzu", "test_turi")
    search_fields = ("matn_uzb", "matn_uz_kr", "matn_rus")
    inlines = [AnswerInline]
    filter_horizontal = ("extra_topics",)
    readonly_fields = ("is_archived",)

    fieldsets = (
        (_("Asosiy ma’lumotlar"), {"fields": ("test_turi", "kategoriya", "mavzu", "extra_topics", "matn_uzb","matn_uz_kr", "matn_rus", "is_archived")}),
        (_("Media fayllar"), {"fields": ("rasm", "audio_uzb", "audio_rus", "video")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TestCategory)
class TestCategoryAdmin(admin.ModelAdmin):
    list_display = ("nomi", "tartib", "aktiv", "show_in_shablon", "show_in_ohshash")
    list_editable = ("tartib", "aktiv", "show_in_shablon", "show_in_ohshash")
    search_fields = ("nomi",)
    fieldsets = (
        (None, {"fields": ("nomi", "tavsif", "tartib", "aktiv")}),
        (_("Ko‘rinish"), {"fields": ("show_in_shablon", "show_in_ohshash")}),
        (_("Parametrlar"), {"fields": ("question_count", "duration_minutes")}),
    )

    def has_delete_permission(self, request, obj=None):
        return (
            obj is not None and not obj.question_set.exists() and not obj.testsession_set.exists()
            and super().has_delete_permission(request, obj)
        )


class TopicInline(admin.TabularInline):
    model = Topic
    fields = ("tartib", "nomi_uzb", "nomi_uz_kr", "nomi_rus", "slug", "aktiv")
    extra = 0


@admin.register(TopicGroup)
class TopicGroupAdmin(admin.ModelAdmin):
    list_display = ("nomi_uzb", "tartib", "icon")
    list_editable = ("tartib",)
    inlines = [TopicInline]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("nomi_uzb", "group", "tartib", "aktiv", "question_count")
    list_editable = ("tartib", "aktiv")
    list_filter = ("group",)
    search_fields = ("nomi_uzb", "nomi_uz_kr", "nomi_rus")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n=Count("questions"))

    @admin.display(description=_("Savollar"), ordering="n")
    def question_count(self, obj):
        return obj.n


@admin.register(TestType)
class TestTypeAdmin(admin.ModelAdmin):
    list_display = ("nomi", "vaqt_daqiqa", "savollar_soni")
    search_fields = ("nomi",)

    def has_delete_permission(self, request, obj=None):
        return obj is not None and not obj.question_set.exists() and super().has_delete_permission(request, obj)


class ExamHistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TestSession)
class TestSessionAdmin(ExamHistoryAdmin):
    list_display = ("user", "category", "test_kind", "source", "started_at", "finished_at")
    list_filter = ("test_kind", "source")
    search_fields = ("user__username", "category__nomi")
    filter_horizontal = ("questions",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__in=students_for(request.user))


@admin.register(UserAnswer)
class UserAnswerAdmin(ExamHistoryAdmin):
    list_display = ("session", "question", "selected_answer", "is_correct")
    list_filter = ("is_correct",)
    search_fields = ("question__matn_uzb", "question__matn_uz_kr", "question__matn_rus")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(session__user__in=students_for(request.user))


@admin.register(SavedQuestion)
class SavedQuestionAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "question__matn")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__in=students_for(request.user))

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)

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
    list_display = ("first_name", "phone", "category", "created_at", "is_handled")
    list_editable = ("is_handled",)
    list_filter = ("is_handled", "category")
    search_fields = ("first_name", "last_name", "phone")


@admin.register(SchoolProfile)
class SchoolProfileAdmin(admin.ModelAdmin):
    """One row: what the public home page says about the school."""
    list_display = ("instructor_name", "phone", "is_demo")
    fieldsets = (
        ("Bosh qism", {"fields": ("instructor_name", "photo", "headline", "headline_kr", "headline_ru",
                                  "intro", "intro_kr", "intro_ru")}),
        ("Raqamlar", {"fields": ("years_experience", "graduates", "pass_rate")}),
        ("Aloqa", {"fields": ("phone", "telegram", "instagram", "address", "address_kr", "address_ru",
                              "hours", "hours_kr", "hours_ru", "map_url")}),
        (None, {"fields": ("is_demo",)}),
    )

    def has_add_permission(self, request):
        return not SchoolProfile.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("category", "title", "price", "duration", "is_popular", "is_active", "order")
    list_editable = ("price", "is_popular", "is_active", "order")
    fieldsets = (
        (None, {"fields": ("category", "price", "is_popular", "is_active", "order")}),
        ("O‘zbekcha", {"fields": ("title", "duration", "features")}),
        ("Ўзбекча (кирил)", {"fields": ("title_kr", "duration_kr", "features_kr")}),
        ("Русский", {"fields": ("title_ru", "duration_ru", "features_ru")}),
    )


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

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk__in=groups_for(request.user))

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)


@admin.register(LoginLock)
class LoginLockAdmin(admin.ModelAdmin):
    """Accounts locked after wrong passwords. Delete a row (or use the action) to let the student in now."""
    list_display = ("username", "status", "level", "last_failure")
    search_fields = ("username",)
    readonly_fields = ("username", "failures", "level", "last_failure", "locked_until")
    actions = ["unlock"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Holati")
    def status(self, obj):
        from django.utils import timezone
        if obj.locked_until and obj.locked_until > timezone.now():
            minutes = int((obj.locked_until - timezone.now()).total_seconds() // 60) + 1
            return f"Bloklangan ({minutes} daqiqa qoldi)"
        return f"Ochiq ({obj.failures} ta xato urinish)"

    @admin.action(description="Blokdan chiqarish")
    def unlock(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} ta hisob blokdan chiqarildi.")
