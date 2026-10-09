from django.urls import path
from push_data_manager.rest_views import views

urlpatterns = [
    path("sync/<str:ats_source>", views.sync_view, name="sync"),
    path("sync/<str:ats_source>/status", views.status_view, name="sync-status"),
]
