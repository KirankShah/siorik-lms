from django.contrib import admin

from .models import OrganizationSettings


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ('organization', 'questions_per_attempt', 'seconds_per_question', 'pass_mark_percent')
