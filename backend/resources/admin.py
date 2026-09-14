from django.contrib import admin

from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'uploaded_by', 'uploaded_at')
    list_filter = ('organization',)
    search_fields = ('title', 'description')
