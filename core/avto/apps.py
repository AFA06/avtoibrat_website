from django.apps import AppConfig


class AvtoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "avto"
    verbose_name = "Sahifa boshqaruvi"

    def ready(self):
        from . import admin_dashboard, signals  # noqa: F401  (signals registers its receivers)
        admin_dashboard.install()
