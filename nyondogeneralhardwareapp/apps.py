from django.apps import AppConfig


class NyondogeneralhardwareappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nyondogeneralhardwareapp'
    def ready(self):
        import nyondogeneralhardwareapp.signals
