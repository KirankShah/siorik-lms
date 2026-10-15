from django.apps import AppConfig


class PeriodicExamsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'periodic_exams'

    def ready(self):
        from . import signals  # noqa: F401
