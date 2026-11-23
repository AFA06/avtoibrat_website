"""Supporting forms linked from Guruhlar and Savollar.

The main admin sections use their own views. Keep only the branch/topic helpers
those forms need; public-site content and exam records have no model-admin UI.
Their models and stored data remain available to the public site and students.
"""
from django.contrib import admin
from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import Branch, Topic, TopicGroup

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
