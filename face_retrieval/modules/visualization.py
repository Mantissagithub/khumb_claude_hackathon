"""Visualisation helpers — all save PNGs to the output dir and return the path.

Confusion matrix, ROC, CMC, retrieval-example montages, false positives /
negatives, similarity-score histogram, detector bounding boxes, and an
embedding scatter via t-SNE (or UMAP if installed).
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _save(fig, out_path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)
    return out_path


def _thumb(path: str, size=160):
    from PIL import Image
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return np.zeros((size, size, 3), np.uint8)
    img.thumbnail((size, size))
    return np.asarray(img)


def plot_cmc(cmc: list, out_path: str) -> str:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(range(1, len(cmc) + 1), cmc, marker="o", ms=3)
    ax.set_xlabel("Rank"); ax.set_ylabel("Identification rate")
    ax.set_title("CMC curve"); ax.set_ylim(0, 1.02); ax.grid(alpha=0.3)
    return _save(fig, out_path)


def plot_roc(roc: dict, auc: float, out_path: str) -> str:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(roc["fpr"], roc["tpr"], label=f"AUC = {auc:.3f}")
    ax.plot([0, 1], [0, 1], "--", color="gray")
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC (verification)"); ax.legend(loc="lower right"); ax.grid(alpha=0.3)
    return _save(fig, out_path)


def plot_similarity_hist(sim: np.ndarray, same: np.ndarray, out_path: str) -> str:
    fig, ax = plt.subplots(figsize=(6, 4))
    g, imp = sim.reshape(-1)[same.reshape(-1)], sim.reshape(-1)[~same.reshape(-1)]
    ax.hist(imp, bins=40, alpha=0.6, label="impostor", density=True)
    ax.hist(g, bins=40, alpha=0.6, label="genuine", density=True)
    ax.set_xlabel("cosine similarity"); ax.set_ylabel("density")
    ax.set_title("Genuine vs impostor scores"); ax.legend()
    return _save(fig, out_path)


def plot_confusion_matrix(true_ids: list, pred_ids: list, out_path: str,
                          max_classes: int = 20) -> str:
    from sklearn.metrics import confusion_matrix
    labels = sorted(set(true_ids))
    if len(labels) > max_classes:
        labels = labels[:max_classes]
    cm = confusion_matrix(true_ids, pred_ids, labels=labels)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90, fontsize=6)
    ax.set_yticklabels(labels, fontsize=6)
    ax.set_xlabel("Predicted (top-1)"); ax.set_ylabel("True")
    ax.set_title(f"Confusion matrix (top {len(labels)} identities)")
    fig.colorbar(im, fraction=0.046)
    return _save(fig, out_path)


def plot_retrieval_example(query_path: str, results: list[dict], out_path: str,
                           title: str = "") -> str:
    """results: [{path, score, correct(bool)}] in rank order."""
    n = len(results) + 1
    fig, axes = plt.subplots(1, n, figsize=(2.0 * n, 2.6))
    axes[0].imshow(_thumb(query_path)); axes[0].set_title("query", fontsize=9)
    axes[0].axis("off")
    for ax, r in zip(axes[1:], results):
        ax.imshow(_thumb(r["path"]))
        color = "limegreen" if r.get("correct") else "red"
        for sp in ax.spines.values():
            sp.set_color(color); sp.set_linewidth(3)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{r['score']:.2f}", fontsize=9, color=color)
    if title:
        fig.suptitle(title, fontsize=10)
    return _save(fig, out_path)


def plot_examples_grid(cases: list[dict], out_path: str, title: str = "") -> str:
    """cases: [{query, retrieved, score, correct}] -> one row each."""
    if not cases:
        return ""
    rows = len(cases)
    fig, axes = plt.subplots(rows, 2, figsize=(4.2, 2.2 * rows))
    if rows == 1:
        axes = axes[None, :]
    for i, c in enumerate(cases):
        axes[i, 0].imshow(_thumb(c["query"])); axes[i, 0].set_title("query", fontsize=8)
        axes[i, 1].imshow(_thumb(c["retrieved"]))
        col = "limegreen" if c.get("correct") else "red"
        axes[i, 1].set_title(f"top-1 {c['score']:.2f}", fontsize=8, color=col)
        for j in (0, 1):
            axes[i, j].axis("off")
    if title:
        fig.suptitle(title, fontsize=11)
    return _save(fig, out_path)


def draw_bboxes(img_rgb: np.ndarray, detections, out_path: str) -> str:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img_rgb)
    for d in detections:
        x1, y1, x2, y2 = d.bbox
        ax.add_patch(plt.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False,
                                   edgecolor="lime", linewidth=2))
        ax.text(x1, max(0, y1 - 4), f"{d.score:.2f}", color="lime", fontsize=8)
    ax.axis("off"); ax.set_title(f"{len(detections)} face(s)")
    return _save(fig, out_path)


def highlight_in_scene(scene_path: str, target_bbox, out_path: str,
                       other_bboxes=None, label: str = "") -> str:
    """Draw the located face (green, labelled) on the crowd frame; other
    detected faces in thin grey — 'your person is HERE in this crowd'."""
    from PIL import Image
    img = np.asarray(Image.open(scene_path).convert("RGB"))
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(img)
    for b in (other_bboxes or []):
        x1, y1, x2, y2 = b
        ax.add_patch(plt.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False,
                                   edgecolor="gray", linewidth=1, alpha=0.6))
    x1, y1, x2, y2 = target_bbox
    ax.add_patch(plt.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False,
                               edgecolor="lime", linewidth=3))
    ax.text(x1, max(0, y1 - 6), label or "match", color="black", fontsize=10,
            bbox=dict(facecolor="lime", edgecolor="none", pad=1))
    ax.axis("off"); ax.set_title("Located in crowd frame")
    return _save(fig, out_path)


def plot_embedding_scatter(embs: np.ndarray, labels: list, out_path: str,
                           method: str = "tsne") -> Optional[str]:
    if len(embs) < 3:
        return None
    method = (method or "tsne").lower()
    coords = None
    if method == "umap":
        try:
            import umap
            coords = umap.UMAP(n_components=2, random_state=42).fit_transform(embs)
        except Exception:
            method = "tsne"
    if coords is None:
        from sklearn.manifold import TSNE
        perp = max(2, min(30, len(embs) - 1))
        coords = TSNE(n_components=2, perplexity=perp, random_state=42,
                      init="random").fit_transform(embs)
    labs = np.asarray(labels)
    uniq = sorted(set(labels))
    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = plt.get_cmap("tab20", len(uniq))
    for i, u in enumerate(uniq):
        m = labs == u
        ax.scatter(coords[m, 0], coords[m, 1], s=18, color=cmap(i),
                   label=str(u) if len(uniq) <= 20 else None)
    ax.set_title(f"Embedding {method.upper()} ({len(uniq)} identities)")
    if len(uniq) <= 20:
        ax.legend(fontsize=6, markerscale=0.8, ncol=2)
    ax.set_xticks([]); ax.set_yticks([])
    return _save(fig, out_path)
