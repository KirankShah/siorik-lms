from django.contrib import admin

from .models import (
    Course,
    CourseAccess,
    DemoLessonAccess,
    Element,
    Enrollment,
    Lesson,
    LessonProgress,
    Module,
    Slide,
    SlideProgress,
    SlideRevision,
    SlideTemplate,
)


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


class SlideInline(admin.TabularInline):
    model = Slide
    extra = 0
    show_change_link = True


@admin.register(SlideTemplate)
class SlideTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'background_css', 'text_color', 'accent_color', 'order')
    ordering = ('order',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'slug',
        'organization',
        'content_owner',
        'is_published',
        'is_demo_available',
        'template',
        'created_by',
        'created_at',
    )
    list_filter = ('content_owner', 'is_published', 'is_demo_available', 'organization', 'template')
    search_fields = ('title', 'slug', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline]


@admin.register(CourseAccess)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = ('course', 'organization', 'granted_at')
    list_filter = ('organization',)
    search_fields = ('course__title', 'organization__name')


@admin.register(DemoLessonAccess)
class DemoLessonAccessAdmin(admin.ModelAdmin):
    list_display = ('course', 'lesson', 'created_at')
    list_filter = ('course',)
    search_fields = ('course__title', 'lesson__title')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'lesson_type', 'order', 'estimated_minutes')
    list_filter = ('lesson_type', 'module__course')
    search_fields = ('title', 'module__title')
    inlines = [SlideInline]


class ElementInline(admin.TabularInline):
    model = Element
    extra = 0
    show_change_link = True


@admin.register(Slide)
class SlideAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'lesson', 'slide_type', 'order', 'template_override', 'estimated_minutes', 'updated_at')
    list_filter = ('slide_type', 'lesson__module__course')
    search_fields = ('title', 'lesson__title')
    inlines = [ElementInline]


@admin.register(Element)
class ElementAdmin(admin.ModelAdmin):
    list_display = ('slide', 'element_type', 'order')
    list_filter = ('element_type', 'slide__lesson__module__course')
    search_fields = ('slide__title', 'rich_text')


@admin.register(SlideRevision)
class SlideRevisionAdmin(admin.ModelAdmin):
    list_display = ('slide', 'edited_by', 'edited_at')
    list_filter = ('slide__lesson__module__course',)
    search_fields = ('slide__title', 'edited_by__email')
    readonly_fields = ('slide', 'elements_json', 'edited_by', 'edited_at')


@admin.register(SlideProgress)
class SlideProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'slide', 'started_at', 'completed_at', 'time_spent_seconds')
    list_filter = ('slide__lesson__module__course',)
    search_fields = ('enrollment__user__email', 'slide__title')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'status', 'progress_percent', 'enrolled_at', 'completed_at')
    list_filter = ('status', 'course')
    search_fields = ('user__email', 'course__title')


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'lesson', 'completed_at', 'time_spent_seconds')
    list_filter = ('lesson__module__course',)
    search_fields = ('enrollment__user__email', 'lesson__title')
