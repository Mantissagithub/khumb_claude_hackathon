"""Configuration loading + runtime helpers (device, seed, logging).

YAML is the single source of truth (config.yaml). `load_config()` deep-merges
the file over built-in defaults so a partial YAML still works.
"""
from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Any, Optional

import yaml

PKG_ROOT = Path(__file__).resolve().parent

DEFAULTS: dict[str, Any] = {
    "project": {"name": "kumbh-reunite", "seed": 42},
    "device": "auto",
    "mixed_precision": True,
    "paths": {"datasets_root": "datasets", "cache_dir": ".cache", "output_dir": "outputs"},
    "detector": {"backend": "auto", "min_face_size": 24, "conf_threshold": 0.6,
                 "det_size": [640, 640]},
    "embedding": {"backend": "auto", "insightface_pack": "buffalo_l",
                  "image_size": 112, "batch_size": 32, "normalize": True, "cache": True},
    "augmentation": {"enabled": True, "probability": 0.5, "seed": 42, "transforms": {}},
    "vector_db": {"backend": "auto", "metric": "cosine", "top_k": 10,
                  "match_threshold": 0.45},
    "camera_network": {"num_cameras": 32, "use_cctv_csv": True,
                       "cctv_csv": "../data/data/CCTV_Locations.csv",
                       "start_time": "2027-07-14T06:00:00",
                       "time_window_minutes": 720, "seed": 42},
    "evaluation": {"top_k": [1, 5, 10], "roc": True, "cmc": True, "embedding_plot": "tsne"},
    "logging": {"level": "INFO"},
}


class DotDict(dict):
    """dict with attribute access, recursively."""

    def __getattr__(self, k):
        try:
            v = self[k]
        except KeyError as e:
            raise AttributeError(k) from e
        return DotDict(v) if isinstance(v, dict) else v

    def __setattr__(self, k, v):
        self[k] = v


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Optional[str] = None) -> DotDict:
    cfg = dict(DEFAULTS)
    p = Path(path) if path else PKG_ROOT / "config.yaml"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            cfg = _deep_merge(cfg, yaml.safe_load(f) or {})
    # resolve relative paths against the package root
    for key in ("datasets_root", "cache_dir", "output_dir"):
        cfg["paths"][key] = str((PKG_ROOT / cfg["paths"][key]).resolve())
    Path(cfg["paths"]["cache_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["paths"]["output_dir"]).mkdir(parents=True, exist_ok=True)
    return DotDict(cfg)


def resolve_device(cfg: dict) -> str:
    want = (cfg.get("device") or "auto").lower()
    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except Exception:
        has_cuda = False
    if want == "cuda" and not has_cuda:
        logging.getLogger("kumbh").warning("CUDA requested but unavailable; using CPU.")
        return "cpu"
    if want == "auto":
        return "cuda" if has_cuda else "cpu"
    return want


def use_amp(cfg: dict, device: str) -> bool:
    """Mixed precision only makes sense on CUDA."""
    return bool(cfg.get("mixed_precision")) and device == "cuda"


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


def get_logger(name: str = "kumbh", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                                         "%H:%M:%S"))
        logger.addHandler(h)
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    return logger
