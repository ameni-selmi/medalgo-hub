from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BenchmarkEntryForm, BenchmarkForm
from .models import Benchmark, BenchmarkEntry, MLModel


def benchmark_list(request):
    qs = Benchmark.objects.filter(status=Benchmark.Status.PUBLISHED).select_related("researcher")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(clinical_task__icontains=q))
    modality = request.GET.get("modality", "").strip()
    if modality:
        qs = qs.filter(modality=modality)

    context = {
        "benchmarks": qs,
        "q": q,
        "active_modality": modality,
        "modalities": MLModel.Modality.choices,
        "count": qs.count(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "benchmarks/_results_grid.html", context)
    return render(request, "benchmarks/list.html", context)


def benchmark_detail(request, slug):
    benchmark = get_object_or_404(
        Benchmark.objects.select_related("researcher").prefetch_related("entries", "entries__model"),
        slug=slug,
    )
    entries = benchmark.entries.all()
    all_metric_keys = set()
    for entry in entries:
        if entry.metrics:
            all_metric_keys.update(entry.metrics.keys())
    metric_keys = sorted(all_metric_keys)

    best_values = {}
    max_values = {}
    for key in metric_keys:
        values = [e.metrics.get(key) for e in entries if e.metrics and e.metrics.get(key) is not None]
        if values:
            best_values[key] = max(values) if key != "inference_time_ms" else min(values)
            max_values[key] = max(values) if max(values) > 0 else 1

    sort_by = request.GET.get("sort", "")
    sort_dir = request.GET.get("dir", "desc")
    if sort_by and sort_by in metric_keys:
        entries_list = sorted(
            entries,
            key=lambda e: e.metrics.get(sort_by, -1) if e.metrics else -1,
            reverse=(sort_dir == "desc"),
        )
    else:
        entries_list = list(entries)

    for entry in entries_list:
        entry.metric_cells = []
        for key in metric_keys:
            val = entry.metrics.get(key) if entry.metrics else None
            is_best = val is not None and best_values.get(key) == val
            max_val = max_values.get(key, 1)
            pct = int(val / max_val * 100) if val is not None and max_val else 0
            entry.metric_cells.append({
                "key": key,
                "value": val,
                "is_best": is_best,
                "bar_pct": pct,
            })

    context = {
        "benchmark": benchmark,
        "entries": entries_list,
        "metric_keys": metric_keys,
        "best_values": best_values,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }
    if request.headers.get("HX-Request"):
        return render(request, "benchmarks/_comparison_table.html", context)
    return render(request, "benchmarks/detail.html", context)


@login_required
def benchmark_create(request):
    profile = getattr(request.user, "researcher_profile", None)
    if not profile or not profile.is_approved:
        return render(request, "benchmarks/create.html", {
            "error": "You must have an approved researcher profile to create benchmarks.",
            "form": None,
        })

    if request.method == "POST":
        form = BenchmarkForm(request.POST)
        if form.is_valid():
            benchmark = form.save(commit=False)
            benchmark.researcher = request.user
            benchmark.status = Benchmark.Status.IN_REVIEW
            benchmark.save()

            entry_idx = 0
            while True:
                prefix = f"entry-{entry_idx}"
                name = request.POST.get(f"{prefix}-model_name")
                if name is None:
                    break
                if not name.strip():
                    entry_idx += 1
                    continue

                metrics_text = request.POST.get(f"{prefix}-metrics_text", "")
                metrics = {}
                for line in metrics_text.strip().split("\n"):
                    line = line.strip()
                    if ":" in line:
                        k, v = line.split(":", 1)
                        try:
                            metrics[k.strip()] = float(v.strip())
                        except ValueError:
                            pass

                model_id = request.POST.get(f"{prefix}-model")
                linked_model = None
                if model_id:
                    try:
                        linked_model = MLModel.objects.get(pk=int(model_id))
                    except (MLModel.DoesNotExist, ValueError):
                        pass

                BenchmarkEntry.objects.create(
                    benchmark=benchmark,
                    model=linked_model,
                    model_name=name.strip(),
                    pipeline_description=request.POST.get(f"{prefix}-pipeline_description", ""),
                    order=entry_idx,
                    metrics=metrics,
                    is_highlighted=request.POST.get(f"{prefix}-is_highlighted") == "on",
                )
                entry_idx += 1

            return redirect("algorithms:benchmark_detail", slug=benchmark.slug)
    else:
        form = BenchmarkForm()

    published_models = MLModel.objects.filter(status=MLModel.Status.PUBLISHED)
    return render(request, "benchmarks/create.html", {
        "form": form,
        "published_models": published_models,
    })


@login_required
def benchmark_edit(request, slug):
    benchmark = get_object_or_404(Benchmark, slug=slug, researcher=request.user)
    if request.method == "POST":
        form = BenchmarkForm(request.POST, instance=benchmark)
        if form.is_valid():
            form.save()
            return redirect("algorithms:benchmark_detail", slug=benchmark.slug)
    else:
        form = BenchmarkForm(instance=benchmark)
    return render(request, "benchmarks/create.html", {
        "form": form,
        "editing": True,
        "benchmark": benchmark,
    })


def benchmark_compare(request, slug):
    benchmark = get_object_or_404(Benchmark, slug=slug)
    entry_ids = request.GET.getlist("entries")
    entries = list(BenchmarkEntry.objects.filter(benchmark=benchmark, pk__in=entry_ids))

    all_metric_keys = set()
    for entry in entries:
        if entry.metrics:
            all_metric_keys.update(entry.metrics.keys())
    metric_keys = sorted(all_metric_keys)

    rows = []
    for key in metric_keys:
        row = {"key": key, "values": []}
        for entry in entries:
            row["values"].append(entry.metrics.get(key) if entry.metrics else None)
        rows.append(row)

    context = {
        "benchmark": benchmark,
        "entries": entries,
        "metric_keys": metric_keys,
        "rows": rows,
    }
    return render(request, "benchmarks/_compare_selected.html", context)
