from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Algorithm, Benchmark, Category, Field, MLModel


def _filtered_algorithms(request):
    """Apply the explore query/filters from GET params."""
    qs = (
        Algorithm.objects.filter(status=Algorithm.Status.PUBLISHED)
        .select_related("category")
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(blurb__icontains=q) | Q(author_handle__icontains=q)
        )
    kind = request.GET.get("kind", "").strip()
    if kind:
        qs = qs.filter(category__kind=kind)
    field = request.GET.get("field", "").strip()
    if field:
        qs = qs.filter(field=field)
    return qs, q, kind, field


def home(request):
    qs = Algorithm.objects.filter(status=Algorithm.Status.PUBLISHED).select_related("category")
    ml_models = MLModel.objects.filter(status=MLModel.Status.PUBLISHED, is_public=True).select_related("researcher")[:6]
    benchmarks = Benchmark.objects.filter(status=Benchmark.Status.PUBLISHED).select_related("researcher")[:3]
    context = {
        "featured": qs.order_by("-installs")[:6],
        "newest": qs.order_by("-created_at")[:4],
        "total": qs.count(),
        "categories": Category.objects.all(),
        "ml_models": ml_models,
        "benchmarks": benchmarks,
    }
    return render(request, "algorithms/home.html", context)


def explore(request):
    qs, q, kind, field = _filtered_algorithms(request)
    context = {
        "algorithms": qs,
        "q": q,
        "active_kind": kind,
        "active_field": field,
        "categories": Category.objects.all(),
        "fields": Field.choices,
        "count": qs.count(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "algorithms/_results.html", context)
    return render(request, "algorithms/explore.html", context)


def detail(request, slug):
    algorithm = get_object_or_404(
        Algorithm.objects.select_related("category", "owner").prefetch_related("versions"),
        slug=slug,
    )
    related_models = MLModel.objects.filter(
        status=MLModel.Status.PUBLISHED, is_public=True
    ).filter(
        Q(clinical_task__icontains=algorithm.name.split()[0]) |
        Q(modality__in=["ct", "mri", "xray"]) & Q(tags__icontains=algorithm.name.split()[0].lower())
    )[:3] if algorithm.field == "medical" else MLModel.objects.none()

    context = {
        "algorithm": algorithm,
        "versions": algorithm.versions.all(),
        "current": algorithm.current_version,
        "related_models": related_models,
    }
    return render(request, "algorithms/detail.html", context)
