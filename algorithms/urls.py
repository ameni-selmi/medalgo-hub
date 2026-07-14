from django.urls import path

from . import views
from . import views_benchmark
from . import views_models

app_name = "algorithms"

urlpatterns = [
    path("", views.home, name="home"),
    path("explore/", views.explore, name="explore"),
    path("algorithm/<slug:slug>/", views.detail, name="detail"),

    # Model hub
    path("models/", views_models.model_list, name="model_list"),
    path("models/upload/", views_models.model_upload, name="model_upload"),
    path("models/<slug:slug>/", views_models.model_detail, name="model_detail"),
    path("models/<slug:slug>/run/", views_models.model_run, name="model_run"),
    path("models/<slug:slug>/demo/", views_models.model_demo, name="model_demo"),
    path("models/<slug:slug>/edit/", views_models.model_edit, name="model_edit"),
    path("runs/<int:run_id>/", views_models.run_result, name="run_result"),
    path("runs/<int:run_id>/status/", views_models.run_status, name="run_status"),

    # Benchmarks
    path("benchmarks/", views_benchmark.benchmark_list, name="benchmark_list"),
    path("benchmarks/create/", views_benchmark.benchmark_create, name="benchmark_create"),
    path("benchmarks/<slug:slug>/", views_benchmark.benchmark_detail, name="benchmark_detail"),
    path("benchmarks/<slug:slug>/edit/", views_benchmark.benchmark_edit, name="benchmark_edit"),
    path("benchmarks/<slug:slug>/compare/", views_benchmark.benchmark_compare, name="benchmark_compare"),
]
