"""High-level pipeline used by the CLI and the notebooks.

Builds a gallery of face embeddings, a FAISS index and a simulated camera
network; searches a missing-person image against it; and runs the full
retrieval + verification evaluation. Augmentation can be applied to queries
to measure robustness to 'Digital Kumbh' degradations.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from .config import PKG_ROOT, resolve_device, use_amp
from .modules import dataset_loader as dl
from .modules.augmentation import KumbhAugmentor
from .modules.camera_sim import (load_cameras, observations_by_embedding,
                                 simulate_observations)
from .modules.embedding import FaceEmbedder, _read_rgb
from .modules.evaluation import Timer, catchtime, cosine_sim_matrix, full_evaluation
from .modules.retrieval import VectorIndex


def collect_samples(cfg, source: str, path: Optional[str], limit: Optional[int]):
    """source: a dataset name, or 'sample' with an explicit folder `path`."""
    if source == "sample":
        return dl.load_sample_folder(path, limit=limit)
    return dl.load_dataset(source, cfg.paths.datasets_root, limit=limit)


class SearchPipeline:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.log = logger
        self.device = resolve_device(cfg)
        self.amp = use_amp(cfg, self.device)
        logger.info("device=%s mixed_precision=%s", self.device, self.amp)
        self.embedder = FaceEmbedder(cfg.embedding, cfg.detector, self.device,
                                     cfg.paths.cache_dir, self.amp, logger)
        self.gallery_paths: list[str] = []
        self.gallery_ids: list = []
        self.gallery_embs: Optional[np.ndarray] = None
        self.index: Optional[VectorIndex] = None
        self.observations: dict[int, dict] = {}

    # -- build --------------------------------------------------------------
    def build_gallery(self, samples) -> None:
        paths = [s.image_path for s in samples]
        self.log.info("embedding %d gallery images ...", len(paths))
        embs, kept = self.embedder.embed_paths(paths)
        if not kept:
            raise RuntimeError("no faces detected in gallery")
        self.gallery_embs = embs
        self.gallery_paths = [paths[i] for i in kept]
        self.gallery_ids = [samples[i].identity for i in kept]
        self.index = VectorIndex(self.embedder.dim, self.cfg.vector_db.backend,
                                 self.cfg.vector_db.metric, self.log)
        self.index.build_index(embs, list(range(len(kept))))
        obs = simulate_observations(self.cfg.camera_network, str(PKG_ROOT),
                                    list(range(len(kept))))
        self.observations = observations_by_embedding(obs)
        self.log.info("gallery=%d faces, identities=%d, cameras simulated",
                      len(kept), len(set(self.gallery_ids)))

    # -- crowd gallery: detect EVERY face per scene frame -------------------
    def build_crowd_gallery(self, scene_samples) -> None:
        """Each scene frame contributes ALL its faces. Every gallery entry
        stores its source frame, bbox and the frame's camera observation."""
        cams = load_cameras(self.cfg.camera_network, str(PKG_ROOT))
        start = datetime.fromisoformat(self.cfg.camera_network.start_time)
        window = int(self.cfg.camera_network.time_window_minutes)
        rng = np.random.default_rng(int(self.cfg.camera_network.seed))

        embs, meta = [], []
        for k, s in enumerate(scene_samples):
            cam = cams[k % len(cams)]                  # one camera per frame
            ts = (start + timedelta(minutes=float(rng.uniform(0, window)))
                  ).isoformat(timespec="seconds")
            faces = self.embedder.embed_image_faces(s.image_path)
            for v, bbox, score in faces:
                embs.append(v)
                meta.append({"scene_path": s.image_path, "bbox": bbox,
                             "det_score": round(score, 3),
                             "camera_id": cam["camera_id"],
                             "lat": cam["lat"], "lng": cam["lng"], "timestamp": ts})
        if not embs:
            raise RuntimeError("no faces detected across crowd scenes")
        self.gallery_embs = np.vstack(embs).astype("float32")
        self.crowd_meta = meta
        self.index = VectorIndex(self.embedder.dim, self.cfg.vector_db.backend,
                                 self.cfg.vector_db.metric, self.log)
        self.index.build_index(self.gallery_embs, list(range(len(meta))))
        self.log.info("crowd gallery: %d faces across %d frames",
                      len(meta), len(scene_samples))

    def build_gallery_from_video(self, video_path: str, max_frames: int = 40,
                                 every_sec: Optional[float] = None) -> int:
        """Sample frames from a clip, index EVERY face per frame. Each gallery
        entry knows its frame timestamp + bbox, so a hit = 'person appears at
        t=Xs in this frame'."""
        from .modules import video as V
        frame_dir = os.path.join(self.cfg.paths.cache_dir, "frames")
        frames = V.sample_frames(video_path, max_frames=max_frames,
                                 every_sec=every_sec, out_dir=frame_dir)
        embs, meta = [], []
        for fr in frames:
            for v, bbox, score in self.embedder.embed_image_faces(fr["image_path"]):
                embs.append(v)
                meta.append({"scene_path": fr["image_path"], "bbox": bbox,
                             "det_score": round(score, 3), "camera_id": "VIDEO",
                             "time_sec": round(fr["time_sec"], 2),
                             "timestamp": f"t={fr['time_sec']:.1f}s",
                             "frame_idx": fr["frame_idx"]})
        if not embs:
            raise RuntimeError("no faces detected in sampled frames")
        self.gallery_embs = np.vstack(embs).astype("float32")
        self.crowd_meta = meta
        self.index = VectorIndex(self.embedder.dim, self.cfg.vector_db.backend,
                                 self.cfg.vector_db.metric, self.log)
        self.index.build_index(self.gallery_embs, list(range(len(meta))))
        self.log.info("video gallery: %d faces across %d sampled frames",
                      len(meta), len(frames))
        return len(frames)

    def find_in_crowd(self, query_path: str, top_k: Optional[int] = None) -> Optional[dict]:
        """Locate a clean missing-person photo among the crowd faces."""
        top_k = top_k or self.cfg.vector_db.top_k
        q = self.embedder.embed_image(query_path)   # largest face in the query
        if q is None:
            return None
        ranked = self.index.search_ids(q, top_k)[0]
        thr = float(self.cfg.vector_db.get("match_threshold", 0.45))
        matches = []
        for rank, (row, score) in enumerate(ranked, 1):
            m = dict(self.crowd_meta[row])
            m.update({"rank": rank, "score": round(float(score), 4),
                      "confident": float(score) >= thr})
            matches.append(m)
        # never assert a wrong identity: flag when even the best is below threshold
        confident = bool(matches and matches[0]["confident"])
        return {"query": query_path, "matches": matches,
                "confident_match": confident, "threshold": thr}

    # -- search -------------------------------------------------------------
    def search_image(self, image_path: str, top_k: Optional[int] = None,
                     timer: Optional[Timer] = None) -> Optional[dict]:
        top_k = top_k or self.cfg.vector_db.top_k
        with catchtime() as td:
            q = self.embedder.embed_image(image_path)
        if timer is not None:
            timer.detect.append(td.dt)
        if q is None:
            return None
        with catchtime() as tr:
            ranked = self.index.search_ids(q, top_k)[0]
        if timer is not None:
            timer.retrieve.append(tr.dt)
            timer.query.append(td.dt + tr.dt)
        matches = []
        for rank, (gid, score) in enumerate(ranked, 1):
            matches.append({
                "rank": rank, "score": round(float(score), 4),
                "identity": self.gallery_ids[gid],
                "gallery_path": self.gallery_paths[gid],
                "observation": self.observations.get(gid),
            })
        return {"query": image_path, "matches": matches}

    # -- evaluate -----------------------------------------------------------
    def evaluate(self, samples, query_per_id: int = 1, augment_queries: bool = False):
        gallery, query = dl.split_gallery_query(samples, query_per_id,
                                                int(self.cfg.project.seed))
        if not query:
            raise RuntimeError("need >=2 images per identity to form queries")
        self.build_gallery(gallery)

        aug = KumbhAugmentor(self.cfg.augmentation) if augment_queries else None
        q_embs, q_ids, q_paths = [], [], []
        timer = Timer()
        for s in query:
            img = _read_rgb(s.image_path)
            if img is None:
                continue
            if aug is not None:
                img, _ = aug.apply(img)
            with catchtime() as td:
                v = self.embedder.embed_image(img)
            timer.detect.append(td.dt)
            if v is None:
                continue
            q_embs.append(v); q_ids.append(s.identity); q_paths.append(s.image_path)
            timer.query.append(td.dt)
        if not q_embs:
            raise RuntimeError("no query faces detected")
        q_embs = np.vstack(q_embs)

        metrics = full_evaluation(q_embs, q_ids, self.gallery_embs, self.gallery_ids,
                                  top_k=tuple(self.cfg.evaluation.top_k), timer=timer)
        # extras for visualisation
        sim = cosine_sim_matrix(q_embs, self.gallery_embs)
        order = np.argsort(-sim, axis=1)
        pred_ids = [self.gallery_ids[order[i, 0]] for i in range(len(q_ids))]
        same = (np.asarray(q_ids)[:, None] == np.asarray(self.gallery_ids)[None, :])
        artifacts = {
            "sim": sim, "same": same, "order": order,
            "query_paths": q_paths,
            "query_ids": q_ids, "pred_ids": pred_ids,
            "query_embs": q_embs,
        }
        return metrics, artifacts
