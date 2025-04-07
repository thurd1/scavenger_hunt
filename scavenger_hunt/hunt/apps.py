from django.apps import AppConfig


class HuntConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hunt'
    
    def ready(self):
        # Import and register signals
        import hunt.signals