"""Face embedding with caching + batch inference.

Backends (auto-selected):
  insightface  ArcFace (buffalo_l, 512-d) — detection+recognition in one.   [if installed]
  facenet      facenet-pytorch InceptionResnetV1 (VGGFace2, 512-d) + MTCNN. [fallback]

Embeddings are L2-normalised (so inner product == cosine). Per-image vectors
are cached to disk keyed by absolute path + mtime + backend, so a second run
(or the eval notebook) reloads instantly instead of recomputing.
"""
from __future__ import annotations

import hashlib
import os
import pickle
from typing import Optional

import numpy as np

from .detector import FaceDetector


def _read_rgb(path: str) -> Optional[np.ndarray]:
    try:
        from PIL import Image
        return np.asarray(Image.open(path).convert("RGB"))
    except Exception:
        return None


def _l2norm(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.clip(n, 1e-9, None)


class FaceEmbedder:
    def __init__(self, cfg: dict, det_cfg: dict, device: str = "cpu",
                 cache_dir: str = ".cache", amp: bool = False, logger=None):
        self.cfg = cfg
        self.device = device
        self.amp = amp
        self.log = logger
        self.image_size = int(cfg.get("image_size", 112))
        self.batch_size = int(cfg.get("batch_size", 32))
        self.normalize = bool(cfg.get("normalize", True))
        self.use_cache = bool(cfg.get("cache", True))
        self.backend = self._select(cfg.get("backend", "auto"))
        self.dim = 512
        # ArcFace aligns to 112; FaceNet (InceptionResnetV1) expects 160.
        self.crop_size = 160 if self.backend == "facenet" else self.image_size
        self._detector = None
        self._model = None
        self._cache: dict[str, np.ndarray] = {}
        self._cache_path = os.path.join(cache_dir, f"emb_{self.backend}.pkl")
        self._init_backend(det_cfg)
        self._load_cache()

    # -- backend selection --------------------------------------------------
    def _has(self, mod: str) -> bool:
        import importlib.util
        return importlib.util.find_spec(mod) is not None

    def _select(self, want: str) -> str:
        want = (want or "auto").lower()
        if want != "auto":
            return want
        return "insightface" if self._has("insightface") else "facenet"

    def _init_backend(self, det_cfg: dict):
        if self.backend == "insightface":
            from insightface.app import FaceAnalysis
            ctx = 0 if self.device == "cuda" else -1
            self._model = FaceAnalysis(name=self.cfg.get("insightface_pack", "buffalo_l"))
            self._model.prepare(ctx_id=ctx, det_size=tuple(det_cfg.get("det_size", [640, 640])))
        elif self.backend == "facenet":
            import torch
            from facenet_pytorch import InceptionResnetV1
            self._detector = FaceDetector(det_cfg, device=self.device, logger=self.log)
            self._model = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)
            self._torch = torch
        else:
            raise RuntimeError(f"unknown embedding backend {self.backend}")
        if self.log:
            self.log.info("embedding backend = %s (dim=%d)", self.backend, self.dim)

    # -- cache --------------------------------------------------------------
    def _load_cache(self):
        if self.use_cache and os.path.isfile(self._cache_path):
            try:
                with open(self._cache_path, "rb") as f:
                    self._cache = pickle.load(f)
            except Exception:
                self._cache = {}

    def save_cache(self):
        if not self.use_cache:
            return
        os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        with open(self._cache_path, "wb") as f:
            pickle.dump(self._cache, f)

    def _key(self, path: str) -> str:
        try:
            mt = os.path.getmtime(path)
        except OSError:
            mt = 0
        return hashlib.md5(f"{os.path.abspath(path)}|{mt}|{self.backend}".encode()).hexdigest()

    # -- embedding ----------------------------------------------------------
    def embed_crops(self, crops: list[np.ndarray]) -> np.ndarray:
        """Embed a batch of already-aligned RGB face crops -> [N, dim]."""
        if self.backend == "facenet":
            import numpy as np
            t = self._torch
            arr = np.stack([c.astype("float32") for c in crops])      # N,H,W,3
            x = t.from_numpy(arr).permute(0, 3, 1, 2)                 # N,3,H,W
            x = (x - 127.5) / 128.0
            x = x.to(self.device)
            with t.no_grad():
                if self.amp:
                    with t.autocast(device_type="cuda"):
                        emb = self._model(x)
                else:
                    emb = self._model(x)
            emb = emb.float().cpu().numpy()
        else:  # insightface crops path (rarely used; prefer embed_image)
            from insightface.model_zoo import get_model  # pragma: no cover
            raise NotImplementedError("use embed_image for insightface")
        return _l2norm(emb) if self.normalize else emb

    def embed_image(self, path_or_img) -> Optional[np.ndarray]:
        """Embed the largest face in an image. Returns None if no face."""
        img = _read_rgb(path_or_img) if isinstance(path_or_img, str) else path_or_img
        if img is None:
            return None
        if self.backend == "insightface":
            faces = self._model.get(img[:, :, ::-1])
            if not faces:
                return None
            f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
            v = np.asarray(f.normed_embedding, dtype="float32")
            return _l2norm(v) if self.normalize else v
        # facenet
        aligned = self._detector.detect_align(img, size=self.crop_size)
        if not aligned:
            return None
        return self.embed_crops([aligned[0][1]])[0]

    def embed_paths(self, paths: list[str], show_progress: bool = True):
        """Embed many images with caching + batching.

        Returns (embeddings [M, dim], kept_indices) where kept_indices maps each
        row back to its index in `paths` (images with no detectable face dropped).
        """
        try:
            from tqdm import tqdm
        except Exception:
            def tqdm(x, **k):
                return x

        embs: list[np.ndarray] = []
        kept: list[int] = []
        # facenet: batch the un-cached crops; insightface: per-image.
        pending_crops, pending_idx = [], []

        def flush():
            if not pending_crops:
                return
            vecs = self.embed_crops(pending_crops)
            for j, v in zip(pending_idx, vecs):
                self._cache[self._key(paths[j])] = v
                embs.append(v); kept.append(j)
            pending_crops.clear(); pending_idx.clear()

        for i, p in enumerate(tqdm(paths, disable=not show_progress, desc="embed")):
            ck = self._key(p)
            if self.use_cache and ck in self._cache:
                embs.append(self._cache[ck]); kept.append(i)
                continue
            if self.backend == "insightface":
                v = self.embed_image(p)
                if v is not None:
                    self._cache[ck] = v; embs.append(v); kept.append(i)
                continue
            # facenet: detect+align now, defer the GPU/CPU forward pass to a batch
            img = _read_rgb(p)
            if img is None:
                continue
            aligned = self._detector.detect_align(img, size=self.crop_size)
            if not aligned:
                continue
            pending_crops.append(aligned[0][1]); pending_idx.append(i)
            if len(pending_crops) >= self.batch_size:
                flush()
        flush()
        self.save_cache()
        if not embs:
            return np.zeros((0, self.dim), dtype="float32"), []
        return np.vstack(embs).astype("float32"), kept
