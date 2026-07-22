from django.contrib import admin

from .models import (
    Course,
    CourseAccess,
    Enrollment,
    Lesson,
    LessonProgress,
    Module,
    Page,
    PageProgress,
    PageRevision,
)


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


class PageInline(admin.TabularInline):
    model = Page
    extra = 0
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'slug',
        'organization',
        'content_owner',
        'is_published',
        'created_by',
        'created_at',
    )
    list_filter = ('content_owner', 'is_published', 'organization')
    search_fields = ('title', 'slug', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline]


@admin.register(CourseAccess)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = ('course', 'organization', 'granted_at')
    list_filter = ('organization',)
    search_fields = ('course__title', 'organization__name')


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
    inlines = [PageInline]


class PageRevisionInline(admin.TabularInline):
    model = PageRevision
    extra = 0
    readonly_fields = ('content_json', 'edited_by', 'edited_at')
    can_delete = False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'page_type', 'order', 'estimated_minutes', 'updated_at')
    list_filter = ('page_type', 'lesson__module__course')
    search_fields = ('title', 'lesson__title')
    inlines = [PageRevisionInline]


@admin.register(PageRevision)
class PageRevisionAdmin(admin.ModelAdmin):
    list_display = ('page', 'edited_by', 'edited_at')
    list_filter = ('page__lesson__module__course',)
    search_fields = ('page__title', 'edited_by__email')


@admin.register(PageProgress)
class PageProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'page', 'started_at', 'completed_at', 'time_spent_seconds')
    list_filter = ('page__lesson__module__course',)
    search_fields = ('enrollment__user__email', 'page__title')


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
