from django.apps import AppConfig


class AutosalonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "autosalon"
    verbose_name = "Автосалон «Атлас Авто»"

    def ready(self):
        from . import signals  # noqa: F401
