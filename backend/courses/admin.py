from django.contrib import admin

from .models import Course, CourseAccess, Enrollment, Lesson, LessonProgress, Module


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


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
