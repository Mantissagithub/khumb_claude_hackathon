"""Dataset ingestion with auto-detection.

Supported (placed under <datasets_root>/<name>/):
  lfw          identity folders  -> face retrieval
  vggface2     {train,test}/<id> -> face retrieval
  widerface    WIDER_*/ + split  -> face DETECTION (gt bboxes)
  crowdhuman   Images/ + *.odgt  -> person/head DETECTION
  market1501   bounding_box_*/   -> person ReID (optional)
  msmt17       train/test + list -> person ReID (optional)

Only datasets actually present on disk are loaded. A generic SampleFolder
loader also handles any local identity-labelled folder for quick tests.
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


@dataclass
class Sample:
    image_path: str
    identity: Optional[str] = None     # None for detection-only datasets
    dataset: str = ""
    bbox: Optional[list] = None        # [x, y, w, h] gt box(es) for detection
    extra: dict = field(default_factory=dict)


# --- detection -------------------------------------------------------------
def available_datasets(root: str) -> dict[str, bool]:
    checks = {
        "lfw": ["lfw"],
        "vggface2": ["vggface2"],
        "widerface": ["widerface"],
        "crowdhuman": ["crowdhuman"],
        "market1501": ["market1501"],
        "msmt17": ["msmt17"],
    }
    out = {}
    for name, subs in checks.items():
        p = os.path.join(root, *subs)
        out[name] = os.path.isdir(p) and bool(os.listdir(p)) if os.path.isdir(p) else False
    return out


def _images_under(path: str) -> list[str]:
    out = []
    for ext in IMG_EXT:
        out += glob.glob(os.path.join(path, "**", "*" + ext), recursive=True)
    return sorted(out)


# --- identity datasets (retrieval) -----------------------------------------
def load_lfw(root: str, limit: Optional[int] = None) -> list[Sample]:
    base = os.path.join(root, "lfw")
    samples = []
    for person in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        pdir = os.path.join(base, person)
        if not os.path.isdir(pdir):
            continue
        for img in _images_under(pdir):
            samples.append(Sample(img, identity=person, dataset="lfw"))
            if limit and len(samples) >= limit:
                return samples
    return samples


def load_vggface2(root: str, split: str = "test", limit: Optional[int] = None) -> list[Sample]:
    base = os.path.join(root, "vggface2")
    # accept vggface2/<split>/<id> or vggface2/<id>
    roots = [os.path.join(base, split), base]
    samples = []
    for b in roots:
        if not os.path.isdir(b):
            continue
        for ident in sorted(os.listdir(b)):
            idir = os.path.join(b, ident)
            if not os.path.isdir(idir):
                continue
            for img in _images_under(idir):
                samples.append(Sample(img, identity=ident, dataset="vggface2"))
                if limit and len(samples) >= limit:
                    return samples
        if samples:
            break
    return samples


_REID_RE = re.compile(r"^(-?\d+)_c(\d+)")  # 0002_c1s1_000451_03.jpg


def _load_reid(base: str, subdirs: list[str], name: str,
               limit: Optional[int]) -> list[Sample]:
    samples = []
    for sd in subdirs:
        d = os.path.join(base, sd)
        if not os.path.isdir(d):
            continue
        for img in _images_under(d):
            m = _REID_RE.match(os.path.basename(img))
            if not m or m.group(1) in ("-1", "0000"):  # junk/distractor ids
                continue
            cam = m.group(2)
            samples.append(Sample(img, identity=m.group(1), dataset=name,
                                  extra={"camera": cam}))
            if limit and len(samples) >= limit:
                return samples
    return samples


def load_market1501(root: str, limit: Optional[int] = None) -> list[Sample]:
    base = os.path.join(root, "market1501")
    # handle the common nested folder name
    nested = os.path.join(base, "Market-1501-v15.09.15")
    base = nested if os.path.isdir(nested) else base
    return _load_reid(base, ["bounding_box_train", "bounding_box_test", "query"],
                      "market1501", limit)


def load_msmt17(root: str, limit: Optional[int] = None) -> list[Sample]:
    base = os.path.join(root, "msmt17")
    return _load_reid(base, ["train", "test", "mask_train_v2", "mask_test_v2"],
                      "msmt17", limit)


# --- detection datasets ----------------------------------------------------
def load_widerface(root: str, split: str = "val", limit: Optional[int] = None) -> list[Sample]:
    """Parse WIDER FACE gt: lines = path, count, then 'x y w h ...' per face."""
    base = os.path.join(root, "widerface")
    gt = os.path.join(base, "wider_face_split", f"wider_face_{split}_bbx_gt.txt")
    img_root = os.path.join(base, f"WIDER_{split}", "images")
    samples: list[Sample] = []
    if not (os.path.isfile(gt) and os.path.isdir(img_root)):
        return samples
    with open(gt) as f:
        lines = [ln.strip() for ln in f]
    i = 0
    while i < len(lines):
        rel = lines[i]; i += 1
        if not rel.endswith(IMG_EXT):
            continue
        n = int(lines[i] or 0); i += 1
        boxes = []
        for _ in range(max(n, 0)):
            parts = lines[i].split(); i += 1
            boxes.append([int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])])
        if n == 0 and i < len(lines) and lines[i] and len(lines[i].split()) >= 4:
            i += 1  # some files store a dummy 0-box line
        samples.append(Sample(os.path.join(img_root, rel), dataset="widerface",
                              bbox=boxes))
        if limit and len(samples) >= limit:
            break
    return samples


def load_crowdhuman(root: str, limit: Optional[int] = None) -> list[Sample]:
    """Parse CrowdHuman .odgt (one JSON object per line)."""
    base = os.path.join(root, "crowdhuman")
    odgt = (glob.glob(os.path.join(base, "annotation_train.odgt")) +
            glob.glob(os.path.join(base, "annotation_val.odgt")) +
            glob.glob(os.path.join(base, "*.odgt")))
    img_dirs = [d for d in glob.glob(os.path.join(base, "*")) if os.path.isdir(d)]
    samples: list[Sample] = []
    if not odgt:
        return samples
    with open(odgt[0]) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            fid = rec.get("ID", "")
            path = None
            for d in img_dirs:
                cand = os.path.join(d, fid + ".jpg")
                if os.path.isfile(cand):
                    path = cand; break
            if not path:
                continue
            boxes = [g.get("fbox") for g in rec.get("gtboxes", []) if g.get("fbox")]
            samples.append(Sample(path, dataset="crowdhuman", bbox=boxes))
            if limit and len(samples) >= limit:
                break
    return samples


# --- generic local folder (quick tests) ------------------------------------
def load_sample_folder(path: str, limit: Optional[int] = None) -> list[Sample]:
    """Identity = subfolder name, OR (flat files) filename stem minus a
    trailing _<digits> (so 'personA_0.jpg' -> identity 'personA')."""
    samples: list[Sample] = []
    subdirs = [d for d in sorted(os.listdir(path))
               if os.path.isdir(os.path.join(path, d))] if os.path.isdir(path) else []
    if subdirs:
        for ident in subdirs:
            for img in _images_under(os.path.join(path, ident)):
                samples.append(Sample(img, identity=ident, dataset="sample"))
    else:
        for img in _images_under(path):
            stem = os.path.splitext(os.path.basename(img))[0]
            ident = re.sub(r"[_-]?\d+$", "", stem) or stem
            samples.append(Sample(img, identity=ident, dataset="sample"))
    return samples[:limit] if limit else samples


# --- dispatch + split ------------------------------------------------------
RETRIEVAL_LOADERS = {
    "lfw": load_lfw, "vggface2": load_vggface2,
    "market1501": load_market1501, "msmt17": load_msmt17,
}
DETECTION_LOADERS = {"widerface": load_widerface, "crowdhuman": load_crowdhuman}


def load_dataset(name: str, root: str, limit: Optional[int] = None) -> list[Sample]:
    if name in RETRIEVAL_LOADERS:
        return RETRIEVAL_LOADERS[name](root, limit=limit)
    if name in DETECTION_LOADERS:
        return DETECTION_LOADERS[name](root, limit=limit)
    raise ValueError(f"unknown dataset {name}")


def split_gallery_query(samples: list[Sample], query_per_id: int = 1,
                        seed: int = 42) -> tuple[list[Sample], list[Sample]]:
    """Hold out `query_per_id` images per identity as queries; rest = gallery.
    Identities with a single image stay in the gallery (cannot be queried)."""
    import random
    rng = random.Random(seed)
    by_id: dict[str, list[Sample]] = {}
    for s in samples:
        if s.identity is None:
            continue
        by_id.setdefault(s.identity, []).append(s)
    gallery, query = [], []
    for ident, items in by_id.items():
        if len(items) < 2:
            gallery.extend(items)
            continue
        rng.shuffle(items)
        k = min(query_per_id, len(items) - 1)
        query.extend(items[:k])
        gallery.extend(items[k:])
    return gallery, query
