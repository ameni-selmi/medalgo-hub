import os

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Benchmark, BenchmarkEntry, MLModel, ResearcherProfile


class RegistrationForm(UserCreationForm):
    institution = forms.CharField(max_length=200)
    orcid = forms.CharField(max_length=40, required=False)
    bio = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            ResearcherProfile.objects.create(
                user=user,
                institution=self.cleaned_data["institution"],
                orcid=self.cleaned_data.get("orcid", ""),
                bio=self.cleaned_data.get("bio", ""),
            )
        return user


MAX_MODEL_SIZE_BYTES = 500 * 1024 * 1024


class MLModelForm(forms.ModelForm):
    class Meta:
        model = MLModel
        fields = [
            "name", "description", "clinical_task", "modality", "body_region", "tags",
            "architecture", "num_classes", "class_labels", "input_size", "input_channels",
            "custom_architecture_code",
            "preprocessing_mean", "preprocessing_std", "preprocessing_notes",
            "model_file", "model_version", "example_input", "example_expected_label",
            "reported_accuracy", "reported_auc", "reported_f1",
            "reported_dataset", "reported_dataset_size",
            "gradcam_enabled", "gradcam_target_layer",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "custom_architecture_code": forms.Textarea(attrs={"rows": 10, "class": "font-mono text-sm"}),
            "preprocessing_notes": forms.Textarea(attrs={"rows": 3}),
            "tags": forms.TextInput(attrs={"placeholder": "e.g. stroke, ct, brain (comma-separated)"}),
            "class_labels": forms.TextInput(attrs={"placeholder": "e.g. Normal, Stroke (comma-separated)"}),
            "preprocessing_mean": forms.TextInput(attrs={"placeholder": "0.485, 0.456, 0.406"}),
            "preprocessing_std": forms.TextInput(attrs={"placeholder": "0.229, 0.224, 0.225"}),
        }

    def clean_model_file(self):
        f = self.cleaned_data.get("model_file")
        if f:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in (".pt", ".pth"):
                raise ValidationError("Only .pt and .pth files are allowed.")
            if f.size > MAX_MODEL_SIZE_BYTES:
                raise ValidationError("Model file must be under 500 MB.")
        return f

    def clean_tags(self):
        val = self.cleaned_data.get("tags")
        if isinstance(val, str):
            return [t.strip() for t in val.split(",") if t.strip()]
        if isinstance(val, list):
            return val
        return []

    def clean_class_labels(self):
        val = self.cleaned_data.get("class_labels")
        if isinstance(val, str):
            return [t.strip() for t in val.split(",") if t.strip()]
        if isinstance(val, list):
            return val
        return []

    def clean_preprocessing_mean(self):
        val = self.cleaned_data.get("preprocessing_mean")
        if isinstance(val, str) and val.strip():
            try:
                return [float(x.strip()) for x in val.split(",")]
            except ValueError:
                raise ValidationError("Enter comma-separated numbers.")
        if isinstance(val, list):
            return val
        return [0.485, 0.456, 0.406]

    def clean_preprocessing_std(self):
        val = self.cleaned_data.get("preprocessing_std")
        if isinstance(val, str) and val.strip():
            try:
                return [float(x.strip()) for x in val.split(",")]
            except ValueError:
                raise ValidationError("Enter comma-separated numbers.")
        if isinstance(val, list):
            return val
        return [0.229, 0.224, 0.225]

    def clean(self):
        cleaned = super().clean()
        num_classes = cleaned.get("num_classes")
        labels = cleaned.get("class_labels")
        if num_classes and labels and len(labels) != num_classes:
            self.add_error("class_labels", f"Expected {num_classes} labels, got {len(labels)}.")

        arch = cleaned.get("architecture")
        code = cleaned.get("custom_architecture_code", "")
        if arch == "custom" and not code.strip():
            self.add_error("custom_architecture_code", "Custom architecture requires code defining build_model().")
        return cleaned


class InferenceUploadForm(forms.Form):
    image = forms.ImageField()


class BenchmarkForm(forms.ModelForm):
    class Meta:
        model = Benchmark
        fields = [
            "name", "description", "clinical_task", "modality", "body_region",
            "dataset_name", "dataset_description", "dataset_size",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "dataset_description": forms.Textarea(attrs={"rows": 3}),
        }


class BenchmarkEntryForm(forms.ModelForm):
    metrics_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "accuracy: 0.92\nauc: 0.96\nf1: 0.91"}),
        required=False,
        help_text="One metric per line, format: name: value",
    )

    class Meta:
        model = BenchmarkEntry
        fields = ["model_name", "model", "pipeline_description", "order", "is_highlighted"]
        widgets = {
            "pipeline_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["model"].required = False
        self.fields["model"].queryset = MLModel.objects.filter(status=MLModel.Status.PUBLISHED)
        if self.instance and self.instance.pk and self.instance.metrics:
            lines = [f"{k}: {v}" for k, v in self.instance.metrics.items()]
            self.fields["metrics_text"].initial = "\n".join(lines)

    def clean_metrics_text(self):
        text = self.cleaned_data.get("metrics_text", "")
        if not text.strip():
            return {}
        metrics = {}
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                raise ValidationError(f"Invalid line: '{line}'. Use format 'name: value'.")
            key, val = line.split(":", 1)
            try:
                metrics[key.strip()] = float(val.strip())
            except ValueError:
                raise ValidationError(f"Value for '{key.strip()}' must be a number.")
        return metrics

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.metrics = self.cleaned_data.get("metrics_text", {})
        if commit:
            instance.save()
        return instance
