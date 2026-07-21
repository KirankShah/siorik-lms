from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'object_type', 'object_id', 'user')
    list_filter = ('action', 'object_type')
    search_fields = ('object_type', 'object_id', 'user__email')
    readonly_fields = ('user', 'action', 'object_type', 'object_id', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
