from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # This will auto-apply your monkey patch on app load
        import api.patches.journal_entry_patch
