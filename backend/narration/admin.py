from django.contrib import admin

from .models import SlideNarration


@admin.register(SlideNarration)
class SlideNarrationAdmin(admin.ModelAdmin):
    list_display = ('slide', 'language', 'voice_name', 'generated_by', 'generated_at')
    list_filter = ('language',)
    search_fields = ('slide__title',)
