from django.contrib import admin

from .models import ScenarioAttempt, ScenarioChoice, ScenarioNode


class ScenarioChoiceInline(admin.TabularInline):
    model = ScenarioChoice
    fk_name = 'node'
    extra = 0


@admin.register(ScenarioNode)
class ScenarioNodeAdmin(admin.ModelAdmin):
    list_display = ('slide', 'node_key', 'is_start')
    list_filter = ('is_start',)
    search_fields = ('slide__title', 'node_key')
    inlines = [ScenarioChoiceInline]


@admin.register(ScenarioAttempt)
class ScenarioAttemptAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'slide', 'reached_recommended_ending', 'completed_at')
    list_filter = ('reached_recommended_ending', 'slide')
    search_fields = ('enrollment__user__email', 'slide__title')
