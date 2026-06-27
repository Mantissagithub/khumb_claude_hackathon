"""Kumbh-Reunite CLI.

  python -m face_retrieval.cli datasets
  python -m face_retrieval.cli augment  --image face.jpg
  python -m face_retrieval.cli index    --source sample --path ./backend/_testdata/faces
  python -m face_retrieval.cli search   --image query.jpg --top-k 5
  python -m face_retrieval.cli evaluate --source sample --path ./backend/_testdata/faces --augment-queries

Authorized-data only: operates on local benchmark datasets you supply; never
scrapes images or connects to live feeds.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

from .config import get_logger, load_config, resolve_device, set_seed, use_amp
from .modules import dataset_loader as dl
from .modules import visualization as viz
from .modules.augmentation import TRANSFORMS, KumbhAugmentor
from .modules.embedding import FaceEmbedder, _read_rgb
from .modules.retrieval import VectorIndex
from .pipeline import SearchPipeline, collect_samples


def _out(cfg, *p):
    return os.path.join(cfg.paths.output_dir, *p)


def cmd_datasets(cfg, args, log):
    avail = dl.available_datasets(cfg.paths.datasets_root)
    print(f"datasets_root: {cfg.paths.datasets_root}\n")
    for name, ok in avail.items():
        print(f"  [{'x' if ok else ' '}] {name}")
    print("\n(place each dataset under datasets/<name>/ — see datasets/README.md)")


def cmd_augment(cfg, args, log):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    img = _read_rgb(args.image)
    if img is None:
        raise SystemExit(f"cannot read {args.image}")
    aug = KumbhAugmentor(cfg.augmentation)
    names = list(TRANSFORMS)
    n = len(names) + 1
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3 * cols, 3 * rows))
    axes = axes.ravel()
    axes[0].imshow(img); axes[0].set_title("original", fontsize=9); axes[0].axis("off")
    for ax, name in zip(axes[1:], names):
        ax.imshow(aug.apply_one(img.copy(), name))
        ax.set_title(name, fontsize=8); ax.axis("off")
    for ax in axes[n:]:
        ax.axis("off")
    out = args.out or _out(cfg, "augment_grid.png")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    print("saved", out)


def cmd_index(cfg, args, log):
    samples = collect_samples(cfg, args.source, args.path, args.limit)
    if not samples:
        raise SystemExit("no samples found")
    pipe = SearchPipeline(cfg, log)
    pipe.build_gallery(samples)
    base = _out(cfg, "index")
    pipe.index.save_index(base)
    manifest = {"dim": pipe.embedder.dim,
                "paths": pipe.gallery_paths, "ids": pipe.gallery_ids,
                "observations": list(pipe.observations.values())}
    with open(_out(cfg, "gallery_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"index saved -> {base}.*  gallery={pipe.index.size} faces")


def cmd_search(cfg, args, log):
    base = _out(cfg, "index")
    if not os.path.isfile(base + ".meta.pkl"):
        raise SystemExit("no index found — run `index` first")
    index = VectorIndex.load_index(base, logger=log)
    with open(_out(cfg, "gallery_manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    obs_by_eid = {o["embedding_id"]: o for o in man["observations"]}

    device = resolve_device(cfg)
    embedder = FaceEmbedder(cfg.embedding, cfg.detector, device,
                            cfg.paths.cache_dir, use_amp(cfg, device), log)
    q = embedder.embed_image(args.image)
    if q is None:
        raise SystemExit("no face detected in query image")
    ranked = index.search_ids(q, args.top_k or cfg.vector_db.top_k)[0]

    print(f"\nQuery: {args.image}")
    results_for_plot = []
    for rank, (gid, score) in enumerate(ranked, 1):
        ob = obs_by_eid.get(gid, {})
        loc = (f"cam {ob.get('camera_id')} @ ({ob.get('lat')},{ob.get('lng')}) "
               f"{ob.get('timestamp','')}") if ob else "n/a"
        print(f"  #{rank}  id={man['ids'][gid]:<12} score={score:.3f}  seen: {loc}")
        results_for_plot.append({"path": man["paths"][gid], "score": float(score),
                                 "correct": False})
    out = viz.plot_retrieval_example(args.image, results_for_plot,
                                     _out(cfg, "search_result.png"),
                                     title="retrieval (top-k)")
    print("montage:", out)


def cmd_evaluate(cfg, args, log):
    samples = collect_samples(cfg, args.source, args.path, args.limit)
    if not samples:
        raise SystemExit("no samples found")
    pipe = SearchPipeline(cfg, log)
    metrics, art = pipe.evaluate(samples, query_per_id=args.query_per_id,
                                 augment_queries=args.augment_queries)

    with open(_out(cfg, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in metrics.items()}, f, indent=2)

    # plots
    r, v = metrics["retrieval"], metrics["verification"]
    viz.plot_cmc(r["cmc"], _out(cfg, "cmc.png"))
    if "roc" in v:
        viz.plot_roc(v["roc"], v.get("auc", 0.0), _out(cfg, "roc.png"))
    viz.plot_similarity_hist(art["sim"], art["same"], _out(cfg, "sim_hist.png"))
    try:
        viz.plot_confusion_matrix(art["query_ids"], art["pred_ids"],
                                  _out(cfg, "confusion.png"))
    except Exception as e:
        log.warning("confusion matrix skipped: %s", e)
    # correct / incorrect example rows
    cases_ok, cases_bad = [], []
    for i, (qid, pid) in enumerate(zip(art["query_ids"], art["pred_ids"])):
        top_gid = int(art["order"][i, 0])
        case = {"query": art["query_paths"][i], "retrieved": pipe.gallery_paths[top_gid],
                "score": float(art["sim"][i, top_gid]), "correct": qid == pid}
        (cases_ok if qid == pid else cases_bad).append(case)
    if cases_ok:
        viz.plot_examples_grid(cases_ok[:5], _out(cfg, "true_positives.png"),
                               "correct top-1")
    if cases_bad:
        viz.plot_examples_grid(cases_bad[:5], _out(cfg, "false_positives.png"),
                               "incorrect top-1")
    try:
        viz.plot_embedding_scatter(pipe.gallery_embs, pipe.gallery_ids,
                                   _out(cfg, "embeddings.png"),
                                   method=cfg.evaluation.embedding_plot)
    except Exception as e:
        log.warning("embedding scatter skipped: %s", e)

    print("\n=== RETRIEVAL ===")
    for k in sorted(r):
        if k != "cmc":
            print(f"  {k}: {r[k]}")
    print("=== VERIFICATION ===")
    for k in ("auc", "eer", "threshold", "precision", "recall", "f1",
              "genuine_mean", "impostor_mean"):
        if k in v:
            print(f"  {k}: {v[k]}")
    print("=== TIMING ===")
    print(" ", metrics.get("timing"))
    print("\nartifacts + metrics.json ->", cfg.paths.output_dir)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("kumbh-reunite",
                                description="Authorized missing-person face retrieval")
    p.add_argument("--config", default=None, help="path to config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("datasets", help="list locally available datasets")

    a = sub.add_parser("augment", help="render the augmentation grid for one image")
    a.add_argument("--image", required=True)
    a.add_argument("--out", default=None)

    for name in ("index", "evaluate"):
        s = sub.add_parser(name)
        s.add_argument("--source", required=True,
                       help="dataset name (lfw/vggface2/...) or 'sample'")
        s.add_argument("--path", default=None, help="folder for --source sample")
        s.add_argument("--limit", type=int, default=None)
        if name == "evaluate":
            s.add_argument("--query-per-id", type=int, default=1)
            s.add_argument("--augment-queries", action="store_true")

    s = sub.add_parser("search", help="search a query image against a saved index")
    s.add_argument("--image", required=True)
    s.add_argument("--top-k", type=int, default=None)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    set_seed(int(cfg.project.seed))
    log = get_logger("kumbh", cfg.logging.level)
    {"datasets": cmd_datasets, "augment": cmd_augment, "index": cmd_index,
     "search": cmd_search, "evaluate": cmd_evaluate}[args.cmd](cfg, args, log)


if __name__ == "__main__":
    main()
