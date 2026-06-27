# Kumbh-Reunite — Missing-Person Face Retrieval (Research / Benchmark)

A modular pipeline to evaluate whether an **already-reported-missing** person
can be retrieved from **authorized** camera frames, using only **public
benchmark datasets** and local files you supply.

> **Scope & ethics.** This is for research, benchmarking and evaluation of
> retrieval methods. It does **not** scrape images and **never** connects to
> live surveillance feeds. It assumes a person was already reported missing and
> that camera data is used under proper consent/approval. Outputs are ranked
> *candidates* for a human to verify — not automated decisions.

---

## Pipeline

```
 missing-person image
        │  detect (RetinaFace / InsightFace / MTCNN)
        ▼
   aligned face ──► embedding (ArcFace / FaceNet, 512-d, L2-normalised)
        │
        ▼
   FAISS index  ◄── gallery built from datasets (+ simulated camera network)
        │  search top-k (cosine)
        ▼
 ranked matches ──► identity + camera location + timestamp ──► visualise
        │
        ▼
   evaluation: Top-1/5/k · mAP · CMC · ROC/AUC · EER · P/R/F1 · latencies
```

## Modules

| File | Responsibility |
|---|---|
| `config.py` / `config.yaml` | YAML config, device/AMP resolution, seeding, logging |
| `modules/dataset_loader.py` | auto-detect + load WIDER FACE, CrowdHuman, VGGFace2, LFW, Market-1501, MSMT17, or any sample folder |
| `modules/augmentation.py` | "Digital Kumbh" degradations (blur, low light, dust, fog, masks, scarves, occlusion, angles, compression, CCTV noise…) |
| `modules/detector.py` | configurable face detection + ArcFace alignment |
| `modules/embedding.py` | ArcFace / FaceNet embeddings, caching, batch inference |
| `modules/retrieval.py` | FAISS index — `build_index` / `search` / `save_index` / `load_index` (numpy fallback) |
| `modules/camera_sim.py` | simulated camera observations (id, time, GPS, crowd density, confidence, bbox) |
| `modules/evaluation.py` | Top-k, mAP, CMC, ROC/AUC, EER, P/R/F1, latency summaries |
| `modules/visualization.py` | confusion matrix, retrieval montages, FP/FN, ROC/CMC, similarity hist, t-SNE/UMAP, bboxes |
| `pipeline.py` | orchestration used by the CLI + notebooks |
| `cli.py` | command-line entry point |

## Backends (auto-selected, configurable)

- **Detector:** `insightface` → `retinaface` → `yolov11face` → `mtcnn` (fallback).
- **Embedding:** `insightface` ArcFace (preferred) → `facenet-pytorch` FaceNet/VGGFace2 (fallback, rides on torch).
- **Vector DB:** `faiss` → numpy brute-force.

Everything is import-guarded — the pipeline runs CPU-only with the fallbacks,
and uses GPU + mixed precision when `device: cuda` and CUDA are available.

## Install

```bash
cd face_retrieval
pip install -r requirements.txt
# Preferred embedding (best accuracy): pip install insightface onnxruntime
```

## Quick start

```bash
# 1) what's available locally?
python -m face_retrieval.cli datasets

# 2) preview the Digital Kumbh augmentations on one image
python -m face_retrieval.cli augment --image path/to/face.jpg

# 3) build + save an index from a dataset (or a sample folder)
python -m face_retrieval.cli index --source lfw --limit 2000
python -m face_retrieval.cli index --source sample --path ../backend/_testdata/faces

# 4) search a missing-person photo -> ranked matches + camera location/time
python -m face_retrieval.cli search --image query.jpg --top-k 5

# 5) full evaluation (add --augment-queries to stress-test robustness)
python -m face_retrieval.cli evaluate --source lfw --limit 3000 --augment-queries
```

Outputs (metrics + plots) are written to `outputs/`. Notebooks:
`notebooks/inference.ipynb` (search demo) and `notebooks/evaluation.ipynb`
(metrics + curves).

## Find a person *in a crowd*

The real scenario: the **query is one clean photo**, but the person is **one
face among many** in a CCTV/crowd frame. So the gallery is built per-FACE — every
face in every frame is detected, embedded and indexed — and a hit returns the
frame, the face's bounding box, and the camera/time.

```bash
python -m face_retrieval.scripts.find_in_crowd_demo
```
```python
from face_retrieval.pipeline import SearchPipeline
pipe.build_crowd_gallery(scene_samples)        # each frame -> all its faces
res = pipe.find_in_crowd("missing_person.jpg") # clean query -> located in a frame
# res["confident_match"], res["matches"][0] -> {scene_path, bbox, camera_id, lat, lng, timestamp, score}
```

A `match_threshold` (config) gates this: if even the best score is below it,
the result is **"no confident match → human review"** rather than a wrong
identity. Demonstrated finding: a large gallery face matches strongly (~0.78),
but a **tiny** face in a 17-person frame (~12 px) scores low (~0.39) and is
correctly rejected — which is why production wants higher-res frames, the
ArcFace + RetinaFace/SCRFD backends (far better on small faces), and always a
threshold + human verification.

## Configuration (`config.yaml`)

```yaml
detector:   { backend: auto }      # retinaface | insightface | yolov11face | mtcnn
embedding:  { backend: auto }      # insightface | facenet
augmentation: { enabled: true, probability: 0.5 }
vector_db:  { backend: auto, metric: cosine, top_k: 10 }
device: auto                        # auto | cpu | cuda
mixed_precision: true
```

## Metrics produced

Top-1 / Top-5 / Top-k accuracy · mean Average Precision · CMC curve ·
ROC + AUC · Equal Error Rate · Precision / Recall / F1 ·
average detection time · average retrieval time · per-query latency.
