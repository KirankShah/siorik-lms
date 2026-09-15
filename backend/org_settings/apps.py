from django.apps import AppConfig


class OrgSettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'org_settings'

    def ready(self):
        from . import signals  # noqa: F401  (registers the post_save receiver)
