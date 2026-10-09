from django.apps import AppConfig

class DbModelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "push_data_manager.db_models"
    label = "sync"
