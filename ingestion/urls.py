from django.urls import path

from . import views

app_name = "ingestion"

urlpatterns = [
    path("review/", views.review_list, name="review_list"),
    path("review/<int:pk>/", views.review_detail, name="review_detail"),
    path("run-queue/", views.run_queue, name="run_queue"),
]
