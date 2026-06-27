"""Configurable face detection + alignment.

Backends, tried in this order for `auto`:
  insightface  (RetinaFace-style SCRFD + 5-pt landmarks)   [if installed]
  retinaface   (retina-face pip package)                    [if installed]
  yolov11face  (ultralytics YOLO face weights)              [if installed]
  mtcnn        (facenet-pytorch)                             [fallback]

A Detection has bbox=[x1,y1,x2,y2], score, and optional 5-point landmarks.
`detect_align` returns ArcFace-aligned 112x112 (or `size`) crops when
landmarks are available, else a plain bbox crop+resize.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

# Canonical ArcFace 5-point template at 112x112.
ARCFACE_REF = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                        [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32)


@dataclass
class Detection:
    bbox: list      # [x1, y1, x2, y2]
    score: float
    landmarks: Optional[np.ndarray] = None  # (5, 2)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _align(img: np.ndarray, det: Detection, size: int) -> Optional[np.ndarray]:
    try:
        import cv2
    except Exception:
        cv2 = None
    if det.landmarks is not None and cv2 is not None:
        ref = ARCFACE_REF * (size / 112.0)
        M, _ = cv2.estimateAffinePartial2D(det.landmarks.astype(np.float32), ref,
                                           method=cv2.LMEDS)
        if M is not None:
            return cv2.warpAffine(img, M, (size, size), borderValue=0)
    # fallback: bbox crop + resize
    x1, y1, x2, y2 = [int(v) for v in det.bbox]
    x1, y1 = max(0, x1), max(0, y1)
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    if cv2 is not None:
        return cv2.resize(crop, (size, size))
    from PIL import Image
    return np.asarray(Image.fromarray(crop).resize((size, size)))


class FaceDetector:
    def __init__(self, cfg: dict, device: str = "cpu", logger=None):
        self.cfg = cfg
        self.device = device
        self.log = logger
        self.conf = float(cfg.get("conf_threshold", 0.6))
        self.det_size = tuple(cfg.get("det_size", [640, 640]))
        self.backend = self._select(cfg.get("backend", "auto"))
        self._impl = None
        self._init_backend()

    # -- backend selection --------------------------------------------------
    def _has(self, mod: str) -> bool:
        import importlib.util
        return importlib.util.find_spec(mod) is not None

    def _select(self, want: str) -> str:
        want = (want or "auto").lower()
        if want != "auto":
            return want
        if self._has("insightface"):
            return "insightface"
        if self._has("retinaface"):
            return "retinaface"
        if self._has("ultralytics"):
            return "yolov11face"
        return "mtcnn"

    def _init_backend(self):
        if self.backend == "insightface":
            from insightface.app import FaceAnalysis
            ctx = 0 if self.device == "cuda" else -1
            self._impl = FaceAnalysis(name=self.cfg.get("insightface_pack", "buffalo_l"))
            self._impl.prepare(ctx_id=ctx, det_size=self.det_size)
        elif self.backend == "mtcnn":
            from facenet_pytorch import MTCNN
            self._impl = MTCNN(keep_all=True, device=self.device,
                               min_face_size=int(self.cfg.get("min_face_size", 24)),
                               post_process=False)
        elif self.backend == "retinaface":
            from retinaface import RetinaFace
            self._impl = RetinaFace
        elif self.backend == "yolov11face":
            from ultralytics import YOLO
            self._impl = YOLO(self.cfg.get("yolo_weights", "yolov11n-face.pt"))
        else:
            raise RuntimeError(f"unknown detector backend {self.backend}")
        if self.log:
            self.log.info("detector backend = %s", self.backend)

    # -- detection ----------------------------------------------------------
    def detect(self, img_rgb: np.ndarray) -> list[Detection]:
        if self.backend == "insightface":
            faces = self._impl.get(img_rgb[:, :, ::-1])  # insightface wants BGR
            out = []
            for f in faces:
                if f.det_score < self.conf:
                    continue
                out.append(Detection(list(map(float, f.bbox)), float(f.det_score),
                                     getattr(f, "kps", None)))
            return out
        if self.backend == "mtcnn":
            from PIL import Image
            boxes, probs, points = self._impl.detect(Image.fromarray(img_rgb),
                                                     landmarks=True)
            out = []
            if boxes is None:
                return out
            for b, p, pts in zip(boxes, probs, points):
                if p is None or p < self.conf:
                    continue
                out.append(Detection([float(x) for x in b], float(p),
                                     np.asarray(pts, dtype=np.float32)))
            return out
        if self.backend == "retinaface":
            res = self._impl.detect_faces(img_rgb)
            out = []
            for _, f in (res or {}).items():
                if f["score"] < self.conf:
                    continue
                x1, y1, x2, y2 = f["facial_area"]
                lm = f.get("landmarks", {})
                kps = np.array([lm[k] for k in ("right_eye", "left_eye", "nose",
                               "mouth_right", "mouth_left")], np.float32) if lm else None
                out.append(Detection([x1, y1, x2, y2], float(f["score"]), kps))
            return out
        if self.backend == "yolov11face":
            res = self._impl(img_rgb, verbose=False)[0]
            out = []
            for b in res.boxes:
                conf = float(b.conf[0])
                if conf < self.conf:
                    continue
                out.append(Detection([float(v) for v in b.xyxy[0]], conf, None))
            return out
        return []

    def detect_align(self, img_rgb: np.ndarray, size: int = 112):
        """Return [(Detection, aligned_crop_rgb)] sorted by area (largest first)."""
        dets = sorted(self.detect(img_rgb), key=lambda d: d.area, reverse=True)
        out = []
        for d in dets:
            crop = _align(img_rgb, d, size)
            if crop is not None:
                out.append((d, crop))
        return out
