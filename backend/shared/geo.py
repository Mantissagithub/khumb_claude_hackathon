"""Resolve a free-text `last_seen_location` to (lat, lng, zone).

The dataset is the Nashik / Trimbakeshwar Kumbh region. We keep a curated lookup
for the ~20 known landmarks and fall back to a deterministic zone-centroid hash
for anything unseen, so every case gets plottable coordinates without a network
geocoder.
"""

from __future__ import annotations

# Curated coordinates for the recurring landmarks in the dataset.
# (lat, lng, zone)
_KNOWN: dict[str, tuple[float, float, str]] = {
    "ramkund ghat": (19.99710, 73.79030, "Zone Area 31"),
    "kushavart kund": (19.93210, 73.52950, "Zone Area 5"),
    "kapila sangam": (20.01390, 73.83440, "Zone Area 26"),
    "takli sangam": (19.96850, 73.82550, "Zone Area 23"),
    "nandur ghat": (20.05020, 73.88220, "Zone Area 7"),
    "dasak ghat": (19.97990, 73.81950, "Zone Area 29"),
    "laxmi narayan ghat": (19.99890, 73.78250, "Zone Area 31"),
    "gauri patangan": (19.99895, 73.86490, "Zone Area 8"),
    "panchavati circle": (20.00070, 73.78250, "Zone Area 30"),
    "trimbakeshwar approach": (19.93210, 73.53000, "Zone Area 5"),
    "trimbak road": (19.98270, 73.71280, "Zone Area 1"),
    "dindori road crossing": (20.07540, 73.80650, "Zone Area 12"),
    "sadhugram gate 1": (20.04890, 73.80450, "Zone Area 2"),
    "sadhugram gate 2": (20.05230, 73.79480, "Zone Area 4"),
    "adgaon parking": (20.05020, 73.88220, "Zone Area 7"),
    "madsangvi transit": (20.00070, 73.86370, "Zone Area 6"),
    "nashik road station": (19.94990, 73.84910, "Zone Area 11"),
    "bus stand nashik": (19.99380, 73.77990, "Zone Area 30"),
    "main police chowki": (19.98370, 73.81920, "Zone Area 21"),
    "rajur bahula": (20.03620, 73.76960, "Zone Area 24"),
}

# Zone centroids (from data/data/Zone_Boundaries.csv) for the deterministic fallback.
_ZONE_CENTROIDS: list[tuple[str, float, float]] = [
    ("Zone Area 1", 19.982676, 73.712825), ("Zone Area 2", 20.04899, 73.804527),
    ("Zone Area 3", 20.04714, 73.800549), ("Zone Area 4", 20.052318, 73.79478),
    ("Zone Area 5", 19.930185, 73.718225), ("Zone Area 6", 20.000705, 73.863689),
    ("Zone Area 7", 20.050195, 73.882161), ("Zone Area 8", 19.998954, 73.864869),
    ("Zone Area 9", 20.02868, 73.718788), ("Zone Area 10", 19.960999, 73.756712),
    ("Zone Area 11", 19.949892, 73.849059), ("Zone Area 12", 20.075429, 73.806543),
]


def resolve(location: str | None) -> tuple[float | None, float | None, str | None]:
    """Return (lat, lng, zone) for a location string, or (None, None, None)."""
    if not location:
        return None, None, None
    key = location.strip().lower()
    if key in _KNOWN:
        lat, lng, zone = _KNOWN[key]
        return lat, lng, zone
    # Substring match against known landmarks (handles minor suffixes/typos).
    for name, (lat, lng, zone) in _KNOWN.items():
        if name in key or key in name:
            return lat, lng, zone
    # Deterministic fallback: hash the text onto a zone centroid.
    idx = sum(ord(c) for c in key) % len(_ZONE_CENTROIDS)
    zone, lat, lng = _ZONE_CENTROIDS[idx]
    return lat, lng, zone
