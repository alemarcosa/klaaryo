from django.apps import AppConfig

class DbModelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "event_logger.db_models"
    label = "event_logger"
