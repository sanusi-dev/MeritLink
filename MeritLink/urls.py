from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    path("ingestion/", include("ingestion.urls", namespace="ingestion")),
    path("scholarships/", include("scholarships.urls", namespace="scholarships")),
]
