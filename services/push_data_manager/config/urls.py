from django.urls import path, include

urlpatterns = [
    path("api/v1/", include("push_data_manager.rest_views.urls")),
]
