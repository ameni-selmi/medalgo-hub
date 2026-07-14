"""
Seed the registry with categories, algorithms, ML models, and benchmarks.

    python manage.py seed

Idempotent: re-running updates existing rows by slug/kind.
"""

import datetime as dt
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from algorithms.models import (
    Algorithm,
    Benchmark,
    BenchmarkEntry,
    Category,
    MLModel,
    ResearcherProfile,
    Version,
)

CATEGORIES = [
    ("engine", "Engines", "Segmentation backbones. Swap nnU-Net for an alternative pipeline.", 0),
    ("architecture", "Architectures", "Model topologies that run inside an engine.", 1),
    ("preprocessor", "Preprocessors", "Data transforms applied before training.", 2),
    ("augmentation", "Augmentations", "Training-time augmentation strategies.", 3),
    ("dataset_adapter", "Dataset Adapters", "Ingest data sources & formats (DICOM, OME-TIFF, GeoTIFF).", 4),
    ("metric", "Metrics", "Evaluation measures and clinical scores.", 5),
    ("postprocessor", "Postprocessors", "Mask refinement after inference.", 6),
    ("exporter", "Exporters", "Output targets — DICOM-SEG, STL, RT-STRUCT.", 7),
    ("domain_pack", "Domain Packs", "Bundled plugins + courses for a field.", 8),
    ("visualizer", "Visualizers", "UI overlays — 3D render, uncertainty heatmaps.", 9),
    ("report", "Reports", "Generated documents and structured reports.", 10),
]

ALGORITHMS = [
    {
        "slug": "nnunet-core", "name": "nnU-Net", "kind": "engine", "field": "medical",
        "author_handle": "segmentforge", "official": True, "verified": True, "license": "Apache-2.0",
        "installs": 48210, "rating": 4.9, "ratings_count": 612,
        "blurb": "The self-configuring reference engine. Fingerprints a dataset and derives the full training plan automatically.",
        "long_description": "nnU-Net analyses your dataset's fingerprint (spacing, intensity distribution, shapes) and self-configures preprocessing, network topology and the training recipe — no manual tuning.",
        "cap_gpu": True, "cap_network": False, "cap_filesystem": "read-write", "cap_data_access": "images-rw",
        "hooks": ["on_fingerprint", "on_plan", "on_train_start", "on_epoch_end", "after_infer"],
        "deps": ["torch>=2.1", "numpy>=1.24", "SimpleITK>=2.3"],
        "versions": [
            {"version": "1.4.2", "released_on": "2026-05-18", "line": "current", "tag": "patch", "diff_summary": "+412 -96", "compat": {"1.2": "warn", "1.3": "ok", "1.4": "ok"}, "notes": ["Fix: planner OOM on >1k-slice CT volumes", "Deterministic seeding across DDP ranks"]},
            {"version": "1.4.0", "released_on": "2026-04-02", "line": "", "tag": "minor", "diff_summary": "+3.1k -880", "compat": {"1.2": "warn", "1.3": "ok", "1.4": "ok"}, "notes": ["Residual encoder presets (M/L/XL)", "2x faster fingerprinting"]},
            {"version": "1.2.0", "released_on": "2025-09-14", "line": "deprecated", "tag": "major", "diff_summary": "+12k", "compat": {"1.2": "ok", "1.3": "bad", "1.4": "bad"}, "notes": ["Initial platform-wrapped release"]},
        ],
    },
    {
        "slug": "swin-unetr", "name": "Swin UNETR", "kind": "architecture", "field": "medical",
        "author_handle": "project-monai", "verified": True, "license": "Apache-2.0",
        "installs": 8330, "rating": 4.5, "ratings_count": 174,
        "blurb": "Shifted-window transformer encoder with a CNN decoder. Robust pretraining.",
        "long_description": "Hierarchical shifted-window transformer encoder paired with a convolutional decoder; ships with self-supervised pretrained weights.",
        "cap_gpu": True, "cap_network": False, "cap_filesystem": "read-only", "cap_data_access": "images-ro",
        "hooks": ["on_plan_override"], "deps": ["torch>=2.1", "monai>=1.3"],
        "versions": [
            {"version": "1.3.2", "released_on": "2026-05-01", "line": "current", "tag": "patch", "diff_summary": "+300 -90", "compat": {"1.2": "warn", "1.3": "ok", "1.4": "ok"}, "notes": ["48-feature preset", "BTCV pretrained weights"]},
        ],
    },
    {
        "slug": "surface-dice", "name": "Surface Dice", "kind": "metric", "field": "medical",
        "author_handle": "jane.doe", "verified": True, "license": "Apache-2.0",
        "installs": 14200, "rating": 4.8, "ratings_count": 330,
        "blurb": "Boundary-aware overlap at a tolerance band. The clinician's metric.",
        "long_description": "Computes the surface Dice coefficient at a configurable tolerance (mm), rewarding boundary accuracy rather than bulk overlap. Reads masks only — never sees raw images.",
        "cap_gpu": False, "cap_network": False, "cap_filesystem": "read-only", "cap_data_access": "masks-only",
        "hooks": ["on_metric_compute"], "deps": ["numpy>=1.24", "scipy>=1.10"],
        "versions": [
            {"version": "1.2.0", "released_on": "2026-05-12", "line": "current", "tag": "minor", "diff_summary": "+120 -60", "compat": {"1.2": "ok", "1.3": "ok", "1.4": "ok"}, "notes": ["Vectorised distance transform (4x faster)", "Per-class tolerance support"]},
        ],
    },
    {
        "slug": "z-norm", "name": "Percentile Z-Norm", "kind": "preprocessor", "field": "generic",
        "author_handle": "segmentforge", "official": True, "verified": True, "license": "Apache-2.0",
        "installs": 21300, "rating": 4.7, "ratings_count": 402,
        "blurb": "Clip to percentile window, then z-score. The default intensity normalizer.",
        "long_description": "Clips intensities to a percentile window then applies z-score normalization. A safe default for most modalities.",
        "cap_gpu": False, "cap_network": False, "cap_filesystem": "read-only", "cap_data_access": "images-ro",
        "hooks": ["before_preprocess"], "deps": ["numpy>=1.24"],
        "versions": [
            {"version": "1.0.3", "released_on": "2026-05-02", "line": "current", "tag": "patch", "diff_summary": "+18 -6", "compat": {"1.2": "ok", "1.3": "ok", "1.4": "ok"}, "notes": ["NaN-safe percentiles"]},
        ],
    },
    {
        "slug": "geotiff-in", "name": "GeoTIFF Adapter", "kind": "dataset_adapter", "field": "remote-sensing",
        "author_handle": "terrasense", "verified": True, "license": "MIT",
        "installs": 1280, "rating": 4.1, "ratings_count": 33,
        "blurb": "Read multi-band GeoTIFF tiles for landcover segmentation.",
        "long_description": "Reads multi-band GeoTIFF tiles with windowed access — proof the core is field-agnostic beyond medical imaging.",
        "cap_gpu": False, "cap_network": False, "cap_filesystem": "read-only", "cap_data_access": "images-ro",
        "hooks": ["on_ingest"], "deps": ["rasterio>=1.3", "numpy>=1.24"],
        "versions": [
            {"version": "0.4.0", "released_on": "2026-03-15", "line": "current", "tag": "minor", "diff_summary": "+80", "compat": {"1.2": "ok", "1.3": "ok", "1.4": "ok"}, "notes": ["Windowed reads"]},
        ],
    },
    {
        "slug": "dicom-seg-out", "name": "DICOM-SEG Exporter", "kind": "exporter", "field": "medical",
        "author_handle": "segmentforge", "official": True, "verified": True, "license": "Apache-2.0",
        "installs": 8800, "rating": 4.6, "ratings_count": 160,
        "blurb": "Write masks back as standards-compliant DICOM-SEG.",
        "long_description": "Exports inference masks as standards-compliant DICOM Segmentation objects with segment colour presets.",
        "cap_gpu": False, "cap_network": False, "cap_filesystem": "read-write", "cap_data_access": "masks-only",
        "hooks": ["on_export"], "deps": ["pydicom>=2.4", "highdicom>=0.22"],
        "versions": [
            {"version": "1.3.0", "released_on": "2026-04-30", "line": "current", "tag": "minor", "diff_summary": "+90 -20", "compat": {"1.2": "ok", "1.3": "ok", "1.4": "ok"}, "notes": ["Segment color presets"]},
        ],
    },
]

ML_MODELS = [
    {
        "slug": "brain-ct-stroke-classifier",
        "name": "Brain CT Stroke Classifier",
        "architecture": "resnet18",
        "num_classes": 2,
        "class_labels": ["Normal", "Stroke"],
        "input_size": 224,
        "input_channels": 3,
        "modality": "ct",
        "body_region": "head",
        "clinical_task": "Ischemic stroke detection from brain CT scans",
        "tags": ["stroke", "ct", "brain", "classification"],
        "description": "A ResNet-18 model fine-tuned for binary classification of brain CT images to detect ischemic stroke. Trained on a curated dataset of clinical brain CT scans.",
        "reported_accuracy": 89.0,
        "reported_auc": 0.93,
        "reported_f1": 0.87,
        "reported_dataset": "CQ500",
        "reported_dataset_size": 491,
        "model_version": "1.0.0",
    },
    {
        "slug": "chest-xray-pneumonia-detector",
        "name": "Chest X-Ray Pneumonia Detector",
        "architecture": "densenet121",
        "num_classes": 2,
        "class_labels": ["Normal", "Pneumonia"],
        "input_size": 224,
        "input_channels": 3,
        "modality": "xray",
        "body_region": "chest",
        "clinical_task": "Pneumonia classification from chest X-rays",
        "tags": ["pneumonia", "xray", "chest", "classification"],
        "description": "A DenseNet-121 model for detecting pneumonia in chest X-ray images. Pre-trained on ImageNet and fine-tuned on chest X-ray datasets.",
        "reported_accuracy": 92.0,
        "reported_auc": 0.96,
        "reported_f1": 0.91,
        "reported_dataset": "RSNA Pneumonia Detection",
        "reported_dataset_size": 26684,
        "model_version": "1.0.0",
    },
    {
        "slug": "skin-lesion-classifier",
        "name": "Skin Lesion Classifier",
        "architecture": "efficientnet_b0",
        "num_classes": 7,
        "class_labels": ["MEL", "NV", "BCC", "AK", "BKL", "DF", "VASC"],
        "input_size": 224,
        "input_channels": 3,
        "modality": "dermoscopy",
        "body_region": "skin",
        "clinical_task": "Multi-class skin lesion classification",
        "tags": ["dermatology", "skin", "lesion", "melanoma", "classification"],
        "description": "An EfficientNet-B0 model for classifying dermoscopic images into 7 categories of skin lesions (ISIC classes). Useful for screening and triage.",
        "reported_accuracy": 85.0,
        "reported_auc": 0.94,
        "reported_f1": 0.83,
        "reported_dataset": "ISIC 2018",
        "reported_dataset_size": 10015,
        "model_version": "1.0.0",
    },
]

BENCHMARKS = [
    {
        "slug": "brain-ct-stroke-classification-benchmark",
        "name": "Brain CT Stroke Classification Benchmark",
        "clinical_task": "Stroke Classification from CT",
        "modality": "ct",
        "body_region": "head",
        "dataset_name": "CQ500",
        "dataset_description": "A curated dataset of 491 brain CT scans from Centre for Advanced Research in Imaging, Neurosciences and Genomics (CARING), New Delhi.",
        "dataset_size": 491,
        "description": "Comparison of deep learning architectures for binary stroke classification on brain CT scans. All models were pre-trained on ImageNet and fine-tuned on the CQ500 dataset.",
        "entries": [
            {"model_name": "ResNet-18 (ImageNet pretrain)", "order": 0, "pipeline_description": "Pretrained on ImageNet, fine-tuned for 50 epochs with AdamW lr=1e-4, augmentations: random flip + rotation", "metrics": {"accuracy": 0.89, "auc": 0.93, "f1": 0.87, "sensitivity": 0.85, "specificity": 0.93, "inference_time_ms": 12}, "link_slug": "brain-ct-stroke-classifier"},
            {"model_name": "ResNet-50 (ImageNet pretrain)", "order": 1, "pipeline_description": "Pretrained on ImageNet, fine-tuned for 30 epochs with AdamW lr=5e-5", "metrics": {"accuracy": 0.92, "auc": 0.96, "f1": 0.91, "sensitivity": 0.90, "specificity": 0.94, "inference_time_ms": 25}},
            {"model_name": "EfficientNet-B0 (ImageNet pretrain)", "order": 2, "pipeline_description": "Pretrained on ImageNet, fine-tuned for 40 epochs with AdamW lr=1e-4", "metrics": {"accuracy": 0.91, "auc": 0.95, "f1": 0.90, "sensitivity": 0.88, "specificity": 0.94, "inference_time_ms": 18}},
            {"model_name": "DenseNet-121 (CheXpert pretrain)", "order": 3, "pipeline_description": "Pretrained on CheXpert chest X-rays, then fine-tuned on brain CTs for 60 epochs", "metrics": {"accuracy": 0.93, "auc": 0.97, "f1": 0.92, "sensitivity": 0.91, "specificity": 0.95, "inference_time_ms": 30}, "is_highlighted": True},
        ],
    },
    {
        "slug": "chest-xray-pneumonia-benchmark",
        "name": "Chest X-Ray Pneumonia Detection Benchmark",
        "clinical_task": "Pneumonia Detection from Chest X-Ray",
        "modality": "xray",
        "body_region": "chest",
        "dataset_name": "RSNA Pneumonia Detection Challenge",
        "dataset_description": "Chest X-ray images from the RSNA Pneumonia Detection Challenge on Kaggle.",
        "dataset_size": 26684,
        "description": "Comparison of architectures for pneumonia detection on chest X-rays from the RSNA challenge dataset.",
        "entries": [
            {"model_name": "DenseNet-121 (ImageNet)", "order": 0, "pipeline_description": "ImageNet pretrained, fine-tuned 30 epochs", "metrics": {"accuracy": 0.92, "auc": 0.96, "f1": 0.91, "inference_time_ms": 28}, "link_slug": "chest-xray-pneumonia-detector"},
            {"model_name": "ResNet-50 (ImageNet)", "order": 1, "pipeline_description": "ImageNet pretrained, fine-tuned 40 epochs", "metrics": {"accuracy": 0.90, "auc": 0.94, "f1": 0.89, "inference_time_ms": 22}},
            {"model_name": "EfficientNet-B2 (ImageNet)", "order": 2, "pipeline_description": "ImageNet pretrained, fine-tuned 35 epochs with mixup augmentation", "metrics": {"accuracy": 0.93, "auc": 0.97, "f1": 0.92, "inference_time_ms": 20}, "is_highlighted": True},
        ],
    },
]


def _create_demo_image(path, size=224):
    """Create a small demo image for the seed model."""
    from PIL import Image
    img = Image.new("RGB", (size, size), color=(128, 128, 128))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


class Command(BaseCommand):
    help = "Seed categories, algorithms, ML models, and benchmarks."

    def handle(self, *args, **options):
        cats = {}
        for kind, label, desc, order in CATEGORIES:
            cat, _ = Category.objects.update_or_create(
                kind=kind, defaults={"label": label, "description": desc, "order": order}
            )
            cats[kind] = cat
        self.stdout.write(self.style.SUCCESS(f"Categories: {len(cats)}"))

        for spec in ALGORITHMS:
            versions = spec.pop("versions", [])
            kind = spec.pop("kind")
            algo, _ = Algorithm.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    **spec,
                    "category": cats[kind],
                    "status": Algorithm.Status.PUBLISHED,
                    "repo_url": f"https://github.com/segmentforge/{spec['slug']}",
                },
            )
            for v in versions:
                Version.objects.update_or_create(
                    algorithm=algo,
                    version=v["version"],
                    defaults={
                        "released_on": dt.date.fromisoformat(v["released_on"]),
                        "line": v["line"],
                        "tag": v["tag"],
                        "diff_summary": v["diff_summary"],
                        "compat": v["compat"],
                        "notes": v["notes"],
                    },
                )
        self.stdout.write(self.style.SUCCESS(f"Algorithms: {len(ALGORITHMS)}"))

        researcher, created = User.objects.get_or_create(
            username="demo_researcher",
            defaults={"email": "researcher@medalgo.dev", "is_staff": False},
        )
        if created:
            researcher.set_password("demo1234")
            researcher.save()
        profile, _ = ResearcherProfile.objects.update_or_create(
            user=researcher,
            defaults={"institution": "MedAlgo Research Lab", "is_approved": True, "bio": "Demo researcher account for seed data."},
        )
        self.stdout.write(self.style.SUCCESS(f"Researcher: {researcher.username}"))

        from django.conf import settings as django_settings
        media_root = str(django_settings.MEDIA_ROOT)

        ml_model_map = {}
        for spec in ML_MODELS:
            import torch
            import torchvision.models as tv_models

            arch = spec["architecture"]
            num_classes = spec["num_classes"]
            slug = spec["slug"]

            pt_dir = os.path.join(media_root, "models", "pt_files")
            os.makedirs(pt_dir, exist_ok=True)
            pt_filename = f"{slug}.pt"
            pt_path = os.path.join(pt_dir, pt_filename)

            if not os.path.exists(pt_path):
                if arch == "resnet18":
                    model = tv_models.resnet18(weights=None)
                    model.fc = torch.nn.Linear(model.fc.in_features, num_classes)
                elif arch == "densenet121":
                    model = tv_models.densenet121(weights=None)
                    model.classifier = torch.nn.Linear(model.classifier.in_features, num_classes)
                elif arch == "efficientnet_b0":
                    model = tv_models.efficientnet_b0(weights=None)
                    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, num_classes)
                else:
                    continue
                torch.save(model.state_dict(), pt_path)
                self.stdout.write(f"  Created {pt_filename}")

            example_dir = os.path.join(media_root, "models", "examples")
            example_path = os.path.join(example_dir, f"{slug}_demo.png")
            if not os.path.exists(example_path):
                _create_demo_image(example_path)

            ml_obj, _ = MLModel.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": spec["name"],
                    "researcher": researcher,
                    "description": spec["description"],
                    "architecture": arch,
                    "num_classes": num_classes,
                    "class_labels": spec["class_labels"],
                    "input_size": spec["input_size"],
                    "input_channels": spec["input_channels"],
                    "modality": spec["modality"],
                    "body_region": spec["body_region"],
                    "clinical_task": spec["clinical_task"],
                    "tags": spec["tags"],
                    "model_file": f"models/pt_files/{pt_filename}",
                    "model_version": spec["model_version"],
                    "example_input": f"models/examples/{slug}_demo.png",
                    "example_expected_label": spec["class_labels"][0],
                    "reported_accuracy": spec.get("reported_accuracy"),
                    "reported_auc": spec.get("reported_auc"),
                    "reported_f1": spec.get("reported_f1"),
                    "reported_dataset": spec.get("reported_dataset", ""),
                    "reported_dataset_size": spec.get("reported_dataset_size"),
                    "status": MLModel.Status.PUBLISHED,
                    "gradcam_enabled": True,
                    "preprocessing_mean": [0.485, 0.456, 0.406],
                    "preprocessing_std": [0.229, 0.224, 0.225],
                },
            )
            ml_model_map[slug] = ml_obj
        self.stdout.write(self.style.SUCCESS(f"ML Models: {len(ML_MODELS)}"))

        for bspec in BENCHMARKS:
            entries = bspec.pop("entries")
            benchmark, _ = Benchmark.objects.update_or_create(
                slug=bspec["slug"],
                defaults={
                    "name": bspec["name"],
                    "researcher": researcher,
                    "clinical_task": bspec["clinical_task"],
                    "modality": bspec["modality"],
                    "body_region": bspec["body_region"],
                    "dataset_name": bspec["dataset_name"],
                    "dataset_description": bspec["dataset_description"],
                    "dataset_size": bspec["dataset_size"],
                    "description": bspec["description"],
                    "status": Benchmark.Status.PUBLISHED,
                },
            )
            for entry_spec in entries:
                linked_model = ml_model_map.get(entry_spec.get("link_slug"))
                BenchmarkEntry.objects.update_or_create(
                    benchmark=benchmark,
                    model_name=entry_spec["model_name"],
                    defaults={
                        "model": linked_model,
                        "order": entry_spec["order"],
                        "pipeline_description": entry_spec.get("pipeline_description", ""),
                        "metrics": entry_spec.get("metrics", {}),
                        "is_highlighted": entry_spec.get("is_highlighted", False),
                    },
                )
        self.stdout.write(self.style.SUCCESS(f"Benchmarks: {len(BENCHMARKS)}"))
        self.stdout.write(self.style.SUCCESS("Seed complete."))
