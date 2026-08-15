from django.contrib import admin

from .models import Character, Scene


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'role')
    list_filter = ('role',)
    search_fields = ('name',)


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ('name', 'scene_type')
    list_filter = ('scene_type',)
    search_fields = ('name',)
