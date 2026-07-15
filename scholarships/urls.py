from django.urls import path

from . import views

app_name = "scholarships"

urlpatterns = [
    path("<int:pk>/queue-recheck/", views.queue_recheck, name="queue_recheck"),
]
