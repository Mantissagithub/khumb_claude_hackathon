"""Retrieval + verification metrics.

Closed-set retrieval (query identity exists in the gallery):
  Top-1 / Top-5 / Top-k accuracy, mean Average Precision (mAP), CMC curve.
Verification (genuine vs impostor pair scores):
  ROC curve + AUC, Equal Error Rate, and Precision/Recall/F1 at a threshold.
Plus helpers to summarise per-stage latency (detection, retrieval, per query).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


# --- timing ----------------------------------------------------------------
@dataclass
class Timer:
    detect: list = field(default_factory=list)
    retrieve: list = field(default_factory=list)
    query: list = field(default_factory=list)

    def summary(self) -> dict:
        def stat(x):
            return {"mean_ms": round(float(np.mean(x)) * 1000, 3),
                    "p95_ms": round(float(np.percentile(x, 95)) * 1000, 3)} if x else {}
        return {"avg_detection": stat(self.detect),
                "avg_retrieval": stat(self.retrieve),
                "latency_per_query": stat(self.query)}


class catchtime:
    """`with catchtime() as t: ...; t.dt` -> elapsed seconds."""
    def __enter__(self):
        self._t = time.perf_counter(); return self

    def __exit__(self, *a):
        self.dt = time.perf_counter() - self._t


# --- retrieval metrics -----------------------------------------------------
def _average_precision(hits: np.ndarray) -> float:
    """hits: boolean array over the ranked gallery (True = same identity)."""
    n_rel = int(hits.sum())
    if n_rel == 0:
        return 0.0
    ranks = np.where(hits)[0] + 1
    precisions = (np.arange(1, n_rel + 1)) / ranks
    return float(precisions.mean())


def retrieval_metrics(sim: np.ndarray, query_ids: list, gallery_ids: list,
                      top_k=(1, 5, 10), cmc_rank: int = 50) -> dict:
    """sim: [Q, G] similarity matrix (higher = closer)."""
    q_ids = np.asarray(query_ids)
    g_ids = np.asarray(gallery_ids)
    order = np.argsort(-sim, axis=1)                 # rank gallery per query
    ranked_ids = g_ids[order]                        # [Q, G]
    match = ranked_ids == q_ids[:, None]             # [Q, G] bool

    first_correct = np.where(match.any(1),
                             match.argmax(1) + 1, np.iinfo(np.int32).max)
    out = {}
    for k in top_k:
        out[f"top{k}"] = round(float(np.mean(first_correct <= k)), 4)
    out["mAP"] = round(float(np.mean([_average_precision(m) for m in match])), 4)

    K = int(min(cmc_rank, sim.shape[1]))
    cmc = [float(np.mean(first_correct <= r)) for r in range(1, K + 1)]
    out["cmc"] = cmc
    out["n_query"], out["n_gallery"] = int(sim.shape[0]), int(sim.shape[1])
    return out


# --- verification metrics --------------------------------------------------
def verification_metrics(sim: np.ndarray, query_ids: list, gallery_ids: list,
                         threshold: float | None = None) -> dict:
    q_ids = np.asarray(query_ids)[:, None]
    g_ids = np.asarray(gallery_ids)[None, :]
    same = (q_ids == g_ids).reshape(-1)
    scores = sim.reshape(-1)

    res: dict = {}
    try:
        from sklearn.metrics import roc_curve, auc, precision_recall_fscore_support
        fpr, tpr, thr = roc_curve(same.astype(int), scores)
        res["roc"] = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}
        res["auc"] = round(float(auc(fpr, tpr)), 4)
        # Equal Error Rate
        fnr = 1 - tpr
        eer_idx = int(np.nanargmin(np.abs(fnr - fpr)))
        res["eer"] = round(float((fpr[eer_idx] + fnr[eer_idx]) / 2), 4)
        if threshold is None:
            threshold = float(thr[eer_idx])
        pred = scores >= threshold
        p, r, f1, _ = precision_recall_fscore_support(
            same, pred, average="binary", zero_division=0)
        res.update({"threshold": round(float(threshold), 4),
                    "precision": round(float(p), 4),
                    "recall": round(float(r), 4),
                    "f1": round(float(f1), 4)})
    except Exception as e:  # sklearn missing -> minimal fallback
        if threshold is None:
            threshold = 0.5
        pred = scores >= threshold
        tp = int((pred & same).sum()); fp = int((pred & ~same).sum())
        fn = int((~pred & same).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        res.update({"threshold": threshold, "precision": round(p, 4),
                    "recall": round(r, 4),
                    "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
                    "note": f"sklearn unavailable: {e}"})
    res["genuine_mean"] = round(float(scores[same].mean()), 4) if same.any() else None
    res["impostor_mean"] = round(float(scores[~same].mean()), 4) if (~same).any() else None
    return res


def cosine_sim_matrix(query_embs: np.ndarray, gallery_embs: np.ndarray) -> np.ndarray:
    """Embeddings are L2-normalised, so this is cosine similarity."""
    return query_embs.astype("float32") @ gallery_embs.astype("float32").T


def full_evaluation(query_embs, query_ids, gallery_embs, gallery_ids,
                    top_k=(1, 5, 10), threshold=None, timer: Timer | None = None) -> dict:
    sim = cosine_sim_matrix(query_embs, gallery_embs)
    out = {"retrieval": retrieval_metrics(sim, query_ids, gallery_ids, top_k),
           "verification": verification_metrics(sim, query_ids, gallery_ids, threshold)}
    if timer is not None:
        out["timing"] = timer.summary()
    return out
