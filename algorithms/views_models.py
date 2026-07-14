import io
import os
import time

import torch
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.contrib.auth import login

from .forms import InferenceUploadForm, MLModelForm, RegistrationForm
from .inference import generate_gradcam, load_model, preprocess_image, run_inference
from .models import InferenceRun, MLModel


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _check_rate_limit(request):
    ip = _get_client_ip(request)
    if not ip:
        return False
    one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
    count = InferenceRun.objects.filter(ip_address=ip, created_at__gte=one_hour_ago).count()
    return count >= 20


def model_list(request):
    qs = MLModel.objects.filter(status=MLModel.Status.PUBLISHED, is_public=True).select_related("researcher")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(clinical_task__icontains=q) | Q(tags__icontains=q)
        )
    modality = request.GET.get("modality", "").strip()
    if modality:
        qs = qs.filter(modality=modality)
    body_region = request.GET.get("body_region", "").strip()
    if body_region:
        qs = qs.filter(body_region=body_region)
    architecture = request.GET.get("architecture", "").strip()
    if architecture:
        qs = qs.filter(architecture=architecture)

    context = {
        "models": qs,
        "q": q,
        "active_modality": modality,
        "active_body_region": body_region,
        "active_architecture": architecture,
        "modalities": MLModel.Modality.choices,
        "body_regions": MLModel.BodyRegion.choices,
        "architectures": MLModel.Architecture.choices,
        "count": qs.count(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "models/_results_grid.html", context)
    return render(request, "models/list.html", context)


@login_required
def model_upload(request):
    profile = getattr(request.user, "researcher_profile", None)
    if not profile or not profile.is_approved:
        return render(request, "models/upload.html", {
            "error": "You must have an approved researcher profile to upload models.",
            "form": None,
        })

    if request.method == "POST":
        form = MLModelForm(request.POST, request.FILES)
        if form.is_valid():
            ml_model = form.save(commit=False)
            ml_model.researcher = request.user
            ml_model.status = MLModel.Status.IN_REVIEW
            ml_model.save()

            try:
                model = load_model(ml_model)
                dummy = torch.randn(1, ml_model.input_channels, ml_model.input_size, ml_model.input_size)
                with torch.no_grad():
                    model(dummy)
            except Exception as e:
                ml_model.delete()
                form.add_error("model_file", f"Model validation failed: {e}")
                return render(request, "models/upload.html", {"form": form})

            return render(request, "models/upload_success.html", {"ml_model": ml_model})
    else:
        form = MLModelForm()

    return render(request, "models/upload.html", {"form": form})


def model_detail(request, slug):
    ml_model = get_object_or_404(
        MLModel.objects.select_related("researcher"),
        slug=slug,
    )
    benchmarks = ml_model.benchmark_entries.select_related("benchmark").filter(
        benchmark__status="published"
    )
    from .models import Algorithm
    related_algos = Algorithm.objects.filter(
        status=Algorithm.Status.PUBLISHED
    ).filter(
        Q(field="medical")
    )[:5]

    context = {
        "ml_model": ml_model,
        "upload_form": InferenceUploadForm(),
        "benchmarks": benchmarks,
        "related_algos": related_algos,
    }
    return render(request, "models/detail.html", context)


def model_run(request, slug):
    ml_model = get_object_or_404(MLModel, slug=slug, status=MLModel.Status.PUBLISHED)

    if _check_rate_limit(request):
        return render(request, "models/_inference_error.html", {
            "error": "Rate limit exceeded. Maximum 20 inference runs per hour. Please try again later."
        })

    if request.method != "POST":
        return redirect("algorithms:model_detail", slug=slug)

    form = InferenceUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "models/_inference_error.html", {
            "error": "Please upload a valid image file."
        })

    run = InferenceRun(
        model=ml_model,
        user=request.user if request.user.is_authenticated else None,
        input_image=form.cleaned_data["image"],
        status=InferenceRun.Status.RUNNING,
        ip_address=_get_client_ip(request),
    )
    run.save()

    try:
        result = run_inference(ml_model, run.input_image.path)
        run.result_label = result["predicted_label"]
        run.result_confidence = result["confidence"]
        run.result_probabilities = result["probabilities"]
        run.inference_time_ms = result["inference_time_ms"]

        if ml_model.gradcam_enabled and ml_model.architecture != "custom":
            try:
                gradcam_img = generate_gradcam(
                    ml_model, run.input_image.path, result["predicted_class_index"]
                )
                if gradcam_img:
                    buf = io.BytesIO()
                    gradcam_img.save(buf, format="PNG")
                    buf.seek(0)
                    run.gradcam_image.save(
                        f"gradcam_{run.pk}.png", ContentFile(buf.read()), save=False
                    )
            except Exception:
                pass

        run.status = InferenceRun.Status.COMPLETED
        run.save()

        return render(request, "models/_inference_result.html", {
            "run": run, "ml_model": ml_model
        })

    except Exception as e:
        run.status = InferenceRun.Status.FAILED
        run.error_message = str(e)
        run.save()
        return render(request, "models/_inference_error.html", {"error": str(e)})


def model_demo(request, slug):
    ml_model = get_object_or_404(MLModel, slug=slug, status=MLModel.Status.PUBLISHED)

    if not ml_model.example_input:
        return render(request, "models/_inference_error.html", {
            "error": "No demo image available for this model."
        })

    if _check_rate_limit(request):
        return render(request, "models/_inference_error.html", {
            "error": "Rate limit exceeded. Maximum 20 inference runs per hour."
        })

    run = InferenceRun(
        model=ml_model,
        user=request.user if request.user.is_authenticated else None,
        input_image=ml_model.example_input,
        status=InferenceRun.Status.RUNNING,
        ip_address=_get_client_ip(request),
    )
    run.save()

    try:
        result = run_inference(ml_model, ml_model.example_input.path)
        run.result_label = result["predicted_label"]
        run.result_confidence = result["confidence"]
        run.result_probabilities = result["probabilities"]
        run.inference_time_ms = result["inference_time_ms"]

        if ml_model.gradcam_enabled and ml_model.architecture != "custom":
            try:
                gradcam_img = generate_gradcam(
                    ml_model, ml_model.example_input.path, result["predicted_class_index"]
                )
                if gradcam_img:
                    buf = io.BytesIO()
                    gradcam_img.save(buf, format="PNG")
                    buf.seek(0)
                    run.gradcam_image.save(
                        f"gradcam_{run.pk}.png", ContentFile(buf.read()), save=False
                    )
            except Exception:
                pass

        run.status = InferenceRun.Status.COMPLETED
        run.save()
        return render(request, "models/_inference_result.html", {
            "run": run, "ml_model": ml_model
        })
    except Exception as e:
        run.status = InferenceRun.Status.FAILED
        run.error_message = str(e)
        run.save()
        return render(request, "models/_inference_error.html", {"error": str(e)})


@login_required
def model_edit(request, slug):
    ml_model = get_object_or_404(MLModel, slug=slug, researcher=request.user)

    if request.method == "POST":
        form = MLModelForm(request.POST, request.FILES, instance=ml_model)
        if form.is_valid():
            form.save()
            return redirect("algorithms:model_detail", slug=ml_model.slug)
    else:
        form = MLModelForm(instance=ml_model)

    return render(request, "models/upload.html", {"form": form, "editing": True, "ml_model": ml_model})


def run_result(request, run_id):
    run = get_object_or_404(InferenceRun.objects.select_related("model"), pk=run_id)
    return render(request, "models/run_detail.html", {"run": run, "ml_model": run.model})


def run_status(request, run_id):
    run = get_object_or_404(InferenceRun, pk=run_id)
    if run.status in (InferenceRun.Status.COMPLETED, InferenceRun.Status.FAILED):
        return render(request, "models/_inference_result.html", {
            "run": run, "ml_model": run.model
        })
    return render(request, "models/_inference_loading.html", {"run": run})


def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("algorithms:home")
    else:
        form = RegistrationForm()
    return render(request, "registration/register.html", {"form": form})
