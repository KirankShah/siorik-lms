from .models import AuditLog


def log_action(user, action, obj):
    """Records an AuditLog entry. `user` may be None for system-initiated actions."""
    AuditLog.objects.create(
        user=user if user and getattr(user, 'is_authenticated', False) else None,
        action=action,
        object_type=obj.__class__.__name__,
        object_id=str(obj.pk),
    )
