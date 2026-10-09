from django.apps import AppConfig

class DbModelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "talent_pool.db_models"
    label = "talent_pool"
