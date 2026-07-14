from django.contrib import admin

from .models import (
    Algorithm,
    Benchmark,
    BenchmarkEntry,
    Category,
    InferenceRun,
    MLModel,
    ResearcherProfile,
    Version,
)


class VersionInline(admin.TabularInline):
    model = Version
    extra = 0
    fields = ("version", "line", "tag", "released_on", "diff_summary", "commit_sha")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("label", "kind", "order")
    prepopulated_fields = {}


@admin.register(Algorithm)
class AlgorithmAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "field", "status", "official", "verified", "installs", "rating")
    list_filter = ("status", "category", "field", "official", "verified")
    search_fields = ("name", "slug", "blurb", "author_handle")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [VersionInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "category", "field", "status")}),
        ("Ownership", {"fields": ("owner", "author_handle", "official", "verified", "license")}),
        ("Content", {"fields": ("blurb", "long_description")}),
        ("Pointers (we host none of these bytes)", {"fields": ("repo_url", "dataset_url", "homepage_url", "docs_url")}),
        ("Declared capabilities", {"fields": ("cap_gpu", "cap_network", "cap_filesystem", "cap_data_access", "hooks", "deps")}),
        ("Community signals", {"fields": ("installs", "rating", "ratings_count")}),
    )


@admin.register(Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = ("algorithm", "version", "line", "tag", "released_on")
    list_filter = ("line", "tag")
    search_fields = ("algorithm__name", "version")


@admin.register(ResearcherProfile)
class ResearcherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "institution", "is_approved")
    list_filter = ("is_approved",)
    search_fields = ("user__username", "institution", "orcid")


class BenchmarkEntryInline(admin.TabularInline):
    model = BenchmarkEntry
    extra = 0
    fields = ("model_name", "model", "order", "is_highlighted")


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display = ("name", "architecture", "modality", "body_region", "status", "researcher", "created_at")
    list_filter = ("status", "modality", "body_region", "architecture")
    search_fields = ("name", "slug", "clinical_task", "researcher__username")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "researcher", "description", "status", "is_public")}),
        ("Architecture", {"fields": ("architecture", "num_classes", "class_labels", "input_size", "input_channels", "custom_architecture_code")}),
        ("Medical Context", {"fields": ("modality", "body_region", "clinical_task", "tags")}),
        ("Model File", {"fields": ("model_file", "model_version")}),
        ("Explainability", {"fields": ("gradcam_enabled", "gradcam_target_layer", "xai_script")}),
        ("Preprocessing", {"fields": ("preprocessing_mean", "preprocessing_std", "preprocessing_notes")}),
        ("Reported Performance", {"fields": ("reported_accuracy", "reported_auc", "reported_f1", "reported_dataset", "reported_dataset_size")}),
        ("Example", {"fields": ("example_input", "example_expected_label")}),
    )


@admin.register(InferenceRun)
class InferenceRunAdmin(admin.ModelAdmin):
    list_display = ("id", "model", "user", "status", "result_label", "result_confidence", "created_at")
    list_filter = ("status",)
    search_fields = ("model__name", "result_label")
    readonly_fields = ("created_at",)


@admin.register(Benchmark)
class BenchmarkAdmin(admin.ModelAdmin):
    list_display = ("name", "clinical_task", "modality", "status", "researcher", "created_at")
    list_filter = ("status", "modality")
    search_fields = ("name", "clinical_task")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BenchmarkEntryInline]


@admin.register(BenchmarkEntry)
class BenchmarkEntryAdmin(admin.ModelAdmin):
    list_display = ("model_name", "benchmark", "order", "is_highlighted")
    list_filter = ("is_highlighted",)
    search_fields = ("model_name", "benchmark__name")
