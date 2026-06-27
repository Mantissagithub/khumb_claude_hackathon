"""'Digital Kumbh' augmentation — simulate real CCTV / crowd degradations.

Each transform maps an RGB uint8 image -> RGB uint8 image. The pipeline applies
each transform independently with its configured probability (config.augmentation),
so you can stress-test how robust the embeddings are to blur, low light, dust,
fog, masks, scarves, occlusion, odd angles, compression and CCTV noise.

Uses OpenCV + numpy. Pure, deterministic given a seed.
"""
from __future__ import annotations

import numpy as np

try:
    import cv2
    _CV2 = True
except Exception:
    _CV2 = False


def _u8(x):
    return np.clip(x, 0, 255).astype(np.uint8)


# --- individual transforms (img: HxWx3 RGB uint8, rng: np.random.Generator) ---
def motion_blur(img, rng):
    k = int(rng.integers(7, 21))
    kernel = np.zeros((k, k), np.float32)
    if rng.random() < 0.5:
        kernel[k // 2, :] = 1.0          # horizontal
    else:
        kernel[:, k // 2] = 1.0          # vertical
    kernel /= k
    return _u8(cv2.filter2D(img, -1, kernel)) if _CV2 else img


def gaussian_blur(img, rng):
    k = int(rng.integers(3, 9)) | 1
    return _u8(cv2.GaussianBlur(img, (k, k), 0)) if _CV2 else img


def low_light(img, rng):
    gain = float(rng.uniform(0.25, 0.55))
    gamma = float(rng.uniform(1.2, 2.0))
    x = (img / 255.0) ** gamma * gain
    return _u8(x * 255)


def bright_sunlight(img, rng):
    gain = float(rng.uniform(1.3, 1.9))
    over = float(rng.uniform(0.0, 0.25))
    x = img.astype(np.float32) * gain + 255 * over
    return _u8(x)


def dust(img, rng):
    h, w = img.shape[:2]
    overlay = img.astype(np.float32).copy()
    n = int(h * w * rng.uniform(0.002, 0.01))
    ys = rng.integers(0, h, n); xs = rng.integers(0, w, n)
    tint = np.array([200, 180, 140], np.float32)   # brown-ish dust
    overlay[ys, xs] = tint
    haze = float(rng.uniform(0.05, 0.2))
    out = overlay * (1 - haze) + tint * haze
    return _u8(out)


def fog(img, rng):
    strength = float(rng.uniform(0.2, 0.5))
    white = np.full_like(img, 235, np.float32)
    return _u8(img.astype(np.float32) * (1 - strength) + white * strength)


def compression(img, rng):
    if not _CV2:
        return img
    q = int(rng.integers(10, 40))
    ok, enc = cv2.imencode(".jpg", img[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, q])
    if not ok:
        return img
    dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return dec[:, :, ::-1]


def cctv_noise(img, rng):
    sigma = float(rng.uniform(8, 25))
    noise = rng.normal(0, sigma, img.shape)
    out = img.astype(np.float32) + noise
    # faint horizontal scanlines
    out[::3, :, :] *= 0.96
    return _u8(out)


def small_face(img, rng):
    if not _CV2:
        return img
    h, w = img.shape[:2]
    f = float(rng.uniform(0.15, 0.4))
    small = cv2.resize(img, (max(1, int(w * f)), max(1, int(h * f))),
                       interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def occlusion(img, rng):
    h, w = img.shape[:2]
    out = img.copy()
    bw, bh = int(w * rng.uniform(0.2, 0.4)), int(h * rng.uniform(0.2, 0.4))
    x, y = int(rng.integers(0, max(1, w - bw))), int(rng.integers(0, max(1, h - bh)))
    color = rng.integers(0, 60, 3)
    out[y:y + bh, x:x + bw] = color
    return out


def face_mask(img, rng):
    """Surgical-style mask over the lower-centre region."""
    h, w = img.shape[:2]
    out = img.copy()
    y0 = int(h * rng.uniform(0.55, 0.62))
    color = np.array([rng.integers(180, 245)] * 3)  # light mask
    out[y0:int(h * 0.9), int(w * 0.2):int(w * 0.8)] = color
    return out


def scarf(img, rng):
    h, w = img.shape[:2]
    out = img.copy()
    y0 = int(h * rng.uniform(0.6, 0.7))
    color = rng.integers(0, 255, 3)
    out[y0:, :] = (out[y0:, :].astype(np.float32) * 0.2 + color * 0.8).astype(np.uint8)
    return out


def umbrella(img, rng):
    if not _CV2:
        return img
    h, w = img.shape[:2]
    out = img.copy()
    color = tuple(int(c) for c in rng.integers(0, 255, 3))
    cv2.ellipse(out, (w // 2, int(h * rng.uniform(0.0, 0.15))),
                (int(w * 0.7), int(h * 0.35)), 0, 0, 360, color, -1)
    return out


def camera_angle(img, rng):
    if not _CV2:
        return img
    h, w = img.shape[:2]
    d = rng.uniform(-0.18, 0.18, 8) * [w, h, w, h, w, h, w, h]
    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst = np.float32([[0 + d[0], 0 + d[1]], [w + d[2], 0 + d[3]],
                      [0 + d[4], h + d[5]], [w + d[6], h + d[7]]])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderValue=0)


def random_crop(img, rng):
    if not _CV2:
        return img
    h, w = img.shape[:2]
    f = float(rng.uniform(0.7, 0.95))
    ch, cw = int(h * f), int(w * f)
    y, x = int(rng.integers(0, h - ch + 1)), int(rng.integers(0, w - cw + 1))
    return cv2.resize(img[y:y + ch, x:x + cw], (w, h))


TRANSFORMS = {
    "motion_blur": motion_blur, "gaussian_blur": gaussian_blur, "low_light": low_light,
    "bright_sunlight": bright_sunlight, "dust": dust, "fog": fog,
    "compression": compression, "cctv_noise": cctv_noise, "small_face": small_face,
    "occlusion": occlusion, "face_mask": face_mask, "scarf": scarf,
    "umbrella": umbrella, "camera_angle": camera_angle, "random_crop": random_crop,
}


class KumbhAugmentor:
    def __init__(self, cfg: dict):
        self.enabled = bool(cfg.get("enabled", True))
        self.default_p = float(cfg.get("probability", 0.5))
        self.overrides = dict(cfg.get("transforms") or {})
        self.rng = np.random.default_rng(int(cfg.get("seed", 42)))

    def p_for(self, name: str) -> float:
        return float(self.overrides.get(name, self.default_p))

    def apply_one(self, img: np.ndarray, name: str) -> np.ndarray:
        return TRANSFORMS[name](img, self.rng)

    def apply(self, img: np.ndarray) -> tuple[np.ndarray, list[str]]:
        """Stochastically apply each enabled transform. Returns (img, applied)."""
        if not self.enabled:
            return img, []
        applied = []
        for name, fn in TRANSFORMS.items():
            if self.rng.random() < self.p_for(name):
                img = fn(img, self.rng)
                applied.append(name)
        return img, applied
