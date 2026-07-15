# MedAlgo Hub

An open **registry, inference, and benchmarking** platform for medical imaging
algorithms. Researchers publish trained PyTorch models, end users run inference
on their own images in the browser, and benchmark suites let the community
compare models side by side.

**Stack:** Django + HTMX + Tailwind. One repo, one process, one deploy.
Server-rendered, no SPA, no separate API. SQLite in dev, Postgres in prod.

## Features

- **Algorithm Registry** — a catalogue of algorithms with versions, a
  compatibility matrix, declared capabilities, dependencies, and rich detail
  pages. Pointers to where code/data live (Git repos, Hugging Face datasets).
- **Model Hub** — researchers upload `.pt` / `.pth` PyTorch model files with
  full metadata (architecture, class labels, preprocessing params). The platform
  loads and runs them for live inference.
- **Live Inference** — any visitor can upload a medical image (JPEG, PNG, DICOM,
  NIfTI) and get classification results instantly, with probability distributions
  and GradCAM explainability overlays.
- **Benchmarking** — researchers create benchmark suites comparing multiple
  models on the same task/dataset, with sortable comparison tables, bar charts,
  and side-by-side comparisons.
- **Auth & Researcher Profiles** — registration creates a researcher profile;
  admin approval is required before uploading models. Inference is open to
  everyone without login.

## Quickstart (dev)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed          # categories, algorithms, ML models, benchmarks
python manage.py createsuperuser   # for /admin
python manage.py runserver
```

Open http://127.0.0.1:8000. The seed command creates:
- 11 algorithm categories and 6 sample algorithms
- A demo researcher account (`demo_researcher` / `demo1234`, pre-approved)
- 3 ML models with real (randomly-initialized) `.pt` files and demo images
- 2 benchmarks with multiple entries and linked models

To test inference: navigate to any model in the Model Hub and click "Try Demo"
or upload your own image.

## Project layout

```
config/                  Django project (settings, urls, wsgi)
algorithms/
  models.py              Algorithm, MLModel, InferenceRun, Benchmark, etc.
  inference.py           Model loading, preprocessing, inference, GradCAM
  views.py               Home, explore, algorithm detail
  views_models.py        Model hub: list, upload, detail, inference, demo
  views_benchmark.py     Benchmark: list, create, detail, compare
  forms.py               Registration, model upload, benchmark forms
  admin.py               Admin for all models
  management/commands/
    seed.py              Seed data (categories, algorithms, models, benchmarks)
    cleanup_old_runs.py  Delete old inference run files (keeps metadata)
templates/
  base.html              Sidebar layout + mobile nav
  algorithms/            Registry templates (home, explore, detail)
  models/                Model hub templates (list, detail, upload, inference)
  benchmarks/            Benchmark templates (list, detail, create, compare)
  registration/          Login and register
media/                   Uploaded model files, images, GradCAM outputs (gitignored)
static/                  Static assets
```

## Data model

- **Category** — 11 plugin kinds (engine, metric, exporter, ...).
- **Algorithm** — registry entry with metadata, pointers, capabilities, versions.
- **Version** — immutable release with compatibility matrix and changelog.
- **ResearcherProfile** — linked to User, requires admin approval to upload.
- **MLModel** — uploaded PyTorch model with architecture, class labels, preprocessing
  params, medical context (modality, body region), reported metrics, and example input.
- **InferenceRun** — records each inference: input image, predicted label, confidence,
  probability distribution, GradCAM image, timing.
- **Benchmark** — comparison suite for a clinical task on a specific dataset.
- **BenchmarkEntry** — one model's results in a benchmark, with flexible metrics.

## Supported architectures

ResNet (18/34/50/101/152), EfficientNet (B0–B7), VGG (16/19), DenseNet
(121/169/201), MobileNet (V2/V3), Inception V3, ViT (B/16, B/32, L/16, L/32),
Swin Transformer (T/S/B), and custom architectures via user-provided code.

## Inference engine

The inference engine (`algorithms/inference.py`) handles:
- **Model loading** with an LRU cache (default 5 models in memory)
- **Image preprocessing** for standard formats, DICOM (via pydicom), and NIfTI (via nibabel)
- **GradCAM visualization** using hook-based gradient computation
- **Custom architectures** via sandboxed `exec()` (restricted builtins, approved researchers only)

CPU-only PyTorch is used by default (much smaller than GPU wheels).

## Security & safety

- Custom architecture `exec()` uses restricted builtins (no `open`, `os`, `sys`, `subprocess`)
- Only admin-approved researchers can upload models or use custom architectures
- Rate limiting: 20 inference runs per IP per hour
- File validation: `.pt`/`.pth` only, max 500 MB, validated with a dummy forward pass on upload
- Research disclaimer shown on every model page and inference result
- `cleanup_old_runs` management command deletes uploaded files after 24 hours

## Production notes

- **Config is env-driven** (`.env.example`). Set `DEBUG=False`, a real
  `SECRET_KEY`, `ALLOWED_HOSTS`, and `DATABASE_URL=postgres://...`.
- **Media files** are stored locally under `media/`. For production, configure
  an external storage backend (S3, GCS) via Django's `STORAGES` setting.
- **Static/CSS without Node.** Dev uses the Tailwind Play CDN. For prod, build
  with the Tailwind standalone CLI:
  ```bash
  ./tailwindcss -i static/src.css -o static/app.css --minify
  ```
- **Deploy:** `docker build -t medalgo-hub . && docker run -p 8000:8000 medalgo-hub`

## License

TBD — must be settled before the first external upload, alongside upload
terms and the per-artifact license field.
