"""Supporting school forms and public homepage content management."""
from django.contrib import admin
from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import Branch, Topic, TopicGroup, TeamMember, Testimonial, GraduateAchievement


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    change_list_template = "admin/homepage_content_list.html"
    list_display = ("full_name", "role", "position")
    list_filter = ("role",)
    search_fields = ("full_name", "position")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    change_list_template = "admin/homepage_content_list.html"
    list_display = ("full_name", "title", "rating")
    search_fields = ("full_name", "text")


@admin.register(GraduateAchievement)
class GraduateAchievementAdmin(admin.ModelAdmin):
    change_list_template = "admin/homepage_content_list.html"
    list_display = ("full_name", "category", "achievement", "graduated_on", "is_published", "order")
    list_editable = ("is_published", "order")
    list_filter = ("is_published", "category")
    search_fields = ("full_name", "achievement")

# Permission-group editing is outside the school panel's current workflow.
admin.site.unregister(Group)


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


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("school_name", "name")
    search_fields = ("school_name", "name")
