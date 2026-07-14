"""
Core registry model.

Design notes
------------
* We are a *registry + knowledge* layer, not a compute platform. An
  ``Algorithm`` points at where its code and data actually live (a Git repo,
  a Hugging Face dataset). We store metadata and pointers, never the heavy
  bytes and never patient data.
* Capabilities (gpu / network / filesystem / data access) are declared, not
  enforced here — they describe what an algorithm *needs* so the catalogue
  can be filtered and, later, so an execution tier can be gated on them.
* ``license`` is required on every algorithm: we redistribute other people's
  work, so each entry must declare under what terms.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    """A kind of plugin (engine, metric, exporter, ...)."""

    class Kind(models.TextChoices):
        ENGINE = "engine", "Engine"
        ARCHITECTURE = "architecture", "Architecture"
        PREPROCESSOR = "preprocessor", "Preprocessor"
        AUGMENTATION = "augmentation", "Augmentation"
        DATASET_ADAPTER = "dataset_adapter", "Dataset Adapter"
        METRIC = "metric", "Metric"
        POSTPROCESSOR = "postprocessor", "Postprocessor"
        EXPORTER = "exporter", "Exporter"
        DOMAIN_PACK = "domain_pack", "Domain Pack"
        VISUALIZER = "visualizer", "Visualizer"
        REPORT = "report", "Report"

    kind = models.CharField(max_length=32, choices=Kind.choices, unique=True)
    label = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["order", "label"]

    def __str__(self):
        return self.label


class Field(models.TextChoices):
    MEDICAL = "medical", "Medical"
    REMOTE_SENSING = "remote-sensing", "Remote sensing"
    MATERIALS = "materials", "Materials"
    GENERIC = "generic", "Generic"


class FileSystemAccess(models.TextChoices):
    NONE = "none", "None"
    READ_ONLY = "read-only", "Read-only"
    READ_WRITE = "read-write", "Read-write"


class DataAccess(models.TextChoices):
    NONE = "none", "None"
    MASKS_ONLY = "masks-only", "Masks only"
    IMAGES_RO = "images-ro", "Images (read-only)"
    IMAGES_RW = "images-rw", "Images (read-write)"


class Algorithm(models.Model):
    """A published (or draft) algorithm / plugin in the registry."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in-review", "In review"
        PUBLISHED = "published", "Published"

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="algorithms")
    field = models.CharField(max_length=24, choices=Field.choices, default=Field.GENERIC)

    # Who owns it on the platform; author_handle is the display credit
    # (may differ, e.g. an org handle, and is kept for seed/imported data).
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="algorithms",
    )
    author_handle = models.CharField(max_length=80, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    official = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)

    # Required: we redistribute other people's work.
    license = models.CharField(max_length=64)

    blurb = models.CharField(max_length=240, help_text="One-line summary for cards.")
    long_description = models.TextField(blank=True, help_text="Markdown. The 'read about it' body.")

    # Pointers — the heavy bytes live elsewhere. We never host them.
    repo_url = models.URLField(blank=True, help_text="Git repo (source of record).")
    dataset_url = models.URLField(blank=True, help_text="Hugging Face / dataset pointer.")
    homepage_url = models.URLField(blank=True)
    docs_url = models.URLField(blank=True)

    # Declared capabilities (filtering + future execution gating).
    cap_gpu = models.BooleanField(default=False)
    cap_network = models.BooleanField(default=False)
    cap_filesystem = models.CharField(
        max_length=16, choices=FileSystemAccess.choices, default=FileSystemAccess.READ_ONLY
    )
    cap_data_access = models.CharField(
        max_length=16, choices=DataAccess.choices, default=DataAccess.NONE
    )

    hooks = models.JSONField(default=list, blank=True, help_text="Lifecycle hook names.")
    deps = models.JSONField(default=list, blank=True, help_text="Dependency specifiers.")

    # Denormalised community signals (cheap to read on list pages).
    installs = models.PositiveIntegerField(default=0)
    rating = models.FloatField(default=0)
    ratings_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-installs", "name"]
        indexes = [
            models.Index(fields=["category", "field"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:80]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("algorithms:detail", args=[self.slug])

    @property
    def current_version(self):
        return self.versions.filter(line=Version.Line.CURRENT).first() or self.versions.first()

    @property
    def is_paid(self):
        return self.license.lower() == "commercial"


class ResearcherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="researcher_profile"
    )
    institution = models.CharField(max_length=200)
    orcid = models.CharField(max_length=40, blank=True)
    bio = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.institution})"


class MLModel(models.Model):
    class Architecture(models.TextChoices):
        RESNET18 = "resnet18", "ResNet-18"
        RESNET34 = "resnet34", "ResNet-34"
        RESNET50 = "resnet50", "ResNet-50"
        RESNET101 = "resnet101", "ResNet-101"
        RESNET152 = "resnet152", "ResNet-152"
        EFFICIENTNET_B0 = "efficientnet_b0", "EfficientNet-B0"
        EFFICIENTNET_B1 = "efficientnet_b1", "EfficientNet-B1"
        EFFICIENTNET_B2 = "efficientnet_b2", "EfficientNet-B2"
        EFFICIENTNET_B3 = "efficientnet_b3", "EfficientNet-B3"
        EFFICIENTNET_B4 = "efficientnet_b4", "EfficientNet-B4"
        EFFICIENTNET_B5 = "efficientnet_b5", "EfficientNet-B5"
        EFFICIENTNET_B6 = "efficientnet_b6", "EfficientNet-B6"
        EFFICIENTNET_B7 = "efficientnet_b7", "EfficientNet-B7"
        VGG16 = "vgg16", "VGG-16"
        VGG19 = "vgg19", "VGG-19"
        DENSENET121 = "densenet121", "DenseNet-121"
        DENSENET169 = "densenet169", "DenseNet-169"
        DENSENET201 = "densenet201", "DenseNet-201"
        MOBILENET_V2 = "mobilenet_v2", "MobileNet V2"
        MOBILENET_V3_SMALL = "mobilenet_v3_small", "MobileNet V3 Small"
        MOBILENET_V3_LARGE = "mobilenet_v3_large", "MobileNet V3 Large"
        INCEPTION_V3 = "inception_v3", "Inception V3"
        VIT_B_16 = "vit_b_16", "ViT-B/16"
        VIT_B_32 = "vit_b_32", "ViT-B/32"
        VIT_L_16 = "vit_l_16", "ViT-L/16"
        VIT_L_32 = "vit_l_32", "ViT-L/32"
        SWIN_T = "swin_t", "Swin-T"
        SWIN_S = "swin_s", "Swin-S"
        SWIN_B = "swin_b", "Swin-B"
        CUSTOM = "custom", "Custom"

    class Modality(models.TextChoices):
        CT = "ct", "CT"
        MRI = "mri", "MRI"
        XRAY = "xray", "X-Ray"
        ULTRASOUND = "ultrasound", "Ultrasound"
        ENDOSCOPY = "endoscopy", "Endoscopy"
        DERMOSCOPY = "dermoscopy", "Dermoscopy"
        FUNDOSCOPY = "fundoscopy", "Fundoscopy"
        HISTOPATHOLOGY = "histopathology", "Histopathology"
        PET = "pet", "PET"
        OTHER = "other", "Other"

    class BodyRegion(models.TextChoices):
        HEAD = "head", "Head"
        CHEST = "chest", "Chest"
        ABDOMEN = "abdomen", "Abdomen"
        PELVIS = "pelvis", "Pelvis"
        SPINE = "spine", "Spine"
        UPPER_EXTREMITY = "upper_extremity", "Upper Extremity"
        LOWER_EXTREMITY = "lower_extremity", "Lower Extremity"
        SKIN = "skin", "Skin"
        EYE = "eye", "Eye"
        WHOLE_BODY = "whole_body", "Whole Body"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In Review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    researcher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ml_models"
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    architecture = models.CharField(max_length=32, choices=Architecture.choices)
    num_classes = models.PositiveIntegerField()
    class_labels = models.JSONField(help_text='List of class label strings, e.g. ["Normal", "Stroke"]')
    input_size = models.PositiveIntegerField(default=224)
    input_channels = models.PositiveIntegerField(default=3)

    modality = models.CharField(max_length=24, choices=Modality.choices)
    body_region = models.CharField(max_length=24, choices=BodyRegion.choices)
    clinical_task = models.CharField(max_length=200)
    tags = models.JSONField(default=list, blank=True)

    model_file = models.FileField(upload_to="models/pt_files/")
    model_version = models.CharField(max_length=32, default="1.0.0")

    custom_architecture_code = models.TextField(blank=True)

    gradcam_enabled = models.BooleanField(default=True)
    gradcam_target_layer = models.CharField(max_length=120, blank=True)
    xai_script = models.TextField(blank=True)

    preprocessing_mean = models.JSONField(default=list, blank=True)
    preprocessing_std = models.JSONField(default=list, blank=True)
    preprocessing_notes = models.TextField(blank=True)

    reported_accuracy = models.FloatField(null=True, blank=True)
    reported_auc = models.FloatField(null=True, blank=True)
    reported_f1 = models.FloatField(null=True, blank=True)
    reported_dataset = models.CharField(max_length=200, blank=True)
    reported_dataset_size = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    is_public = models.BooleanField(default=True)

    example_input = models.ImageField(upload_to="models/examples/", blank=True)
    example_expected_label = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["modality", "body_region"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        if not self.preprocessing_mean:
            self.preprocessing_mean = [0.485, 0.456, 0.406]
        if not self.preprocessing_std:
            self.preprocessing_std = [0.229, 0.224, 0.225]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("algorithms:model_detail", args=[self.slug])


class InferenceRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    model = models.ForeignKey(MLModel, on_delete=models.CASCADE, related_name="runs")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inference_runs"
    )
    input_image = models.ImageField(upload_to="runs/inputs/")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    result_label = models.CharField(max_length=200, blank=True)
    result_confidence = models.FloatField(null=True, blank=True)
    result_probabilities = models.JSONField(null=True, blank=True)
    gradcam_image = models.ImageField(upload_to="runs/gradcam/", blank=True)
    error_message = models.TextField(blank=True)
    inference_time_ms = models.PositiveIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Run #{self.pk} on {self.model.name}"


class Benchmark(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In Review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    researcher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="benchmarks"
    )
    clinical_task = models.CharField(max_length=200)
    modality = models.CharField(max_length=24, choices=MLModel.Modality.choices)
    body_region = models.CharField(max_length=24, choices=MLModel.BodyRegion.choices)
    dataset_name = models.CharField(max_length=200)
    dataset_description = models.TextField(blank=True)
    dataset_size = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("algorithms:benchmark_detail", args=[self.slug])


class BenchmarkEntry(models.Model):
    benchmark = models.ForeignKey(Benchmark, on_delete=models.CASCADE, related_name="entries")
    model = models.ForeignKey(MLModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="benchmark_entries")
    model_name = models.CharField(max_length=200)
    pipeline_description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict, blank=True)
    confusion_matrix = models.JSONField(null=True, blank=True)
    roc_data = models.JSONField(null=True, blank=True)
    training_details = models.JSONField(default=dict, blank=True)
    is_highlighted = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.model_name} in {self.benchmark.name}"


class Version(models.Model):
    """An immutable release of an algorithm, pinned to a source commit."""

    class Line(models.TextChoices):
        CURRENT = "current", "Current"
        STABLE = "", "Stable"
        DEPRECATED = "deprecated", "Deprecated"

    class Tag(models.TextChoices):
        MAJOR = "major", "Major"
        MINOR = "minor", "Minor"
        PATCH = "patch", "Patch"

    algorithm = models.ForeignKey(Algorithm, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=32, help_text="Semver, e.g. 1.4.2")
    released_on = models.DateField(null=True, blank=True)
    line = models.CharField(max_length=16, choices=Line.choices, blank=True, default=Line.STABLE)
    tag = models.CharField(max_length=8, choices=Tag.choices, default=Tag.MINOR)

    commit_sha = models.CharField(max_length=64, blank=True, help_text="Immutable source pointer.")
    diff_summary = models.CharField(max_length=64, blank=True, help_text="e.g. +412 -96")
    notes = models.JSONField(default=list, blank=True, help_text="Changelog bullet points.")

    # Compatibility against each core line: {"1.2": "ok|warn|bad", ...}
    compat = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-released_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["algorithm", "version"], name="unique_algorithm_version"),
        ]

    def __str__(self):
        return f"{self.algorithm.name} {self.version}"
