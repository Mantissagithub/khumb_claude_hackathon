"""Video ingestion — sample frames from a clip so each frame becomes a
'scene' the face pipeline can index.

This turns "is this person in this clip?" into the same per-face retrieval
problem as crowd stills: sample frames, detect every face per frame, embed,
index; a hit then points to a frame + timestamp.

Uses OpenCV (cv2). ffmpeg backend handles mp4 / webm / ogv.
"""
from __future__ import annotations

import os

import numpy as np


def sample_frames(video_path: str, max_frames: int = 40,
                  every_sec: float | None = None, out_dir: str = "frames") -> list[dict]:
    """Return [{frame_idx, time_sec, image_path}] sampled across the clip.

    every_sec: sample one frame every N seconds (then capped at max_frames).
    Otherwise: max_frames evenly spaced across the whole clip.
    """
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if every_sec:
        step = max(1, int(fps * every_sec))
        idxs = list(range(0, total or 10 ** 9, step))
        if max_frames:
            idxs = idxs[:max_frames]
    elif total > 0:
        idxs = np.linspace(0, total - 1, min(max_frames, total)).astype(int).tolist()
    else:
        idxs = list(range(max_frames))

    os.makedirs(out_dir, exist_ok=True)
    out = []
    for i, idx in enumerate(idxs):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok:
            continue
        path = os.path.join(out_dir, f"frame_{i:04d}.jpg")
        cv2.imwrite(path, frame)            # frame is BGR; imwrite expects BGR
        out.append({"frame_idx": int(idx), "time_sec": idx / fps, "image_path": path})
    cap.release()
    return out
