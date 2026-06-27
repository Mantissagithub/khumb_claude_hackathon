"""Fusion engine: combine all signals into one explainable, located match.

Design choices that matter:
  * Dynamic weighting — we re-normalise over only the signals that exist for
    a given pair, so a no-name no-photo report still matches on description +
    geo + demographics instead of being penalised for blank fields.
  * Fully explainable — every result carries a per-signal breakdown and
    human-readable reasons, so an operator (not the machine) decides merges.
  * Located — every result is geo-enriched (zone, nearest police, CCTV) using
    the report's coordinates or its resolved last-seen text.
"""
from __future__ import annotations

from typing import Optional

from .. import config
from ..data_loader import GeoContext
from ..geo import haversine_m
from ..models import Report
from . import cloth, face
from . import text as T


def _as_dict(x) -> dict:
    if isinstance(x, Report):
        return {
            "id": x.id, "source": x.source, "type": x.type, "name": x.name,
            "gender": x.gender, "age_band": x.age_band, "state": x.state,
            "district": x.district, "language": x.language,
            "last_seen_location": x.last_seen_location,
            "reporter_mobile": x.reporter_mobile,
            "physical_description": x.physical_description,
            "lat": x.lat, "lng": x.lng,
            "face_embedding": x.face_embedding,
            "cloth_signature": x.cloth_signature,
        }
    return x


def _colors_of(d: dict) -> set:
    app = d.get("appearance")
    if app and app.get("colors"):
        return set(app["colors"])
    return T.extract_appearance(d.get("physical_description", ""))["colors"]


def _resolve_coords(d: dict, geoctx: GeoContext) -> Optional[tuple[float, float]]:
    lat, lng = d.get("lat"), d.get("lng")
    if lat is not None and lng is not None:
        return float(lat), float(lng)
    txt = d.get("last_seen_location", "")
    return geoctx.resolve_location(txt) if txt else None


def _geo_score(q: dict, c: dict, geoctx: GeoContext) -> Optional[float]:
    qc, cc = _resolve_coords(q, geoctx), _resolve_coords(c, geoctx)
    if not qc or not cc:
        return None
    d = haversine_m(qc[0], qc[1], cc[0], cc[1])
    if d <= 500:
        return 1.0
    if d <= 2000:
        return 0.7
    if d <= 5000:
        return 0.4
    return 0.15


def _cloth_score(q: dict, c: dict) -> Optional[float]:
    qsig, csig = q.get("cloth_signature"), c.get("cloth_signature")
    qcol, ccol = _colors_of(q), _colors_of(c)
    if qsig and csig:
        return cloth.score_sig_sig(qsig, csig)
    if qsig and ccol:
        return cloth.score_sig_text(qsig, ccol)
    if csig and qcol:
        return cloth.score_sig_text(csig, qcol)
    return T.appearance_similarity_text(
        q.get("physical_description", ""), c.get("physical_description", ""))


def _reasons(b: dict) -> list[str]:
    out = []
    f = b.get("face")
    if f is not None and f >= 0.7:
        out.append(f"Face strongly matches ({f:.2f})")
    elif f is not None and f >= 0.5:
        out.append(f"Face likely matches ({f:.2f})")
    if b.get("mobile") == 1.0:
        out.append("Mobile number matches")
    if b.get("name") is not None and b["name"] >= 0.85:
        out.append(f"Name matches closely ({b['name']:.2f})")
    if b.get("cloth") is not None and b["cloth"] >= 0.55:
        out.append(f"Clothing / appearance matches ({b['cloth']:.2f})")
    if b.get("demographics") is not None and b["demographics"] >= 0.8:
        out.append("Same gender / age band / origin")
    if b.get("geo") is not None and b["geo"] >= 0.7:
        out.append("Reported very near each other")
    if b.get("description") is not None and b["description"] >= 0.7:
        out.append("Physical descriptions align")
    return out


def score_pair(query, candidate, geoctx: GeoContext) -> dict:
    """Score a query report against one candidate. Returns fused result."""
    q, c = _as_dict(query), _as_dict(candidate)
    qd, cd = q.get("physical_description", ""), c.get("physical_description", "")

    raw = {
        "face": face.score(q.get("face_embedding"), c.get("face_embedding")),
        "cloth": _cloth_score(q, c),
        "name": T.name_score(q.get("name", ""), c.get("name", "")),
        "mobile": T.mobile_score(q.get("reporter_mobile", ""), c.get("reporter_mobile", "")),
        "demographics": T.demographics_score(q, c),
        "description": T.description_score(qd, cd),
        "geo": _geo_score(q, c, geoctx),
    }

    wsum, ssum, breakdown = 0.0, 0.0, {}
    for key, val in raw.items():
        if val is None:
            continue
        w = config.WEIGHTS[key]
        wsum += w
        ssum += w * val
        breakdown[key] = round(val, 3)

    total = round(ssum / wsum, 4) if wsum else 0.0
    if total >= config.AUTO_REVIEW:
        band = "review_queue"
    elif total >= config.SHOW:
        band = "candidate"
    else:
        band = "weak"

    return {
        "candidate_id": c.get("id") or c.get("case_id"),
        "source": c.get("source", "live"),
        "score": total,
        "decision": band,
        "breakdown": breakdown,
        "reasons": _reasons(breakdown),
        "location": geoctx.enrich(c.get("lat"), c.get("lng"),
                                  c.get("last_seen_location", "")),
        "candidate": {k: c.get(k) for k in (
            "case_id", "id", "type", "name", "gender", "age_band", "state",
            "district", "language", "last_seen_location", "status")},
    }


class MatchEngine:
    def __init__(self, store, geoctx: GeoContext):
        self.store = store
        self.geo = geoctx

    def _pool(self, query: dict, scope: str) -> list:
        """Pick candidate records to compare against.

        For a FOUND person we search MISSING reports (and vice-versa); for
        dedup we also compare against same-type live reports.
        """
        qtype = query.get("type", "missing")
        opp = "found" if qtype == "missing" else "missing"
        pools: list = []
        if scope in ("all", "government"):
            # registry rows are 'missing' records; useful when query is 'found'
            pools += self.store.government
        if scope in ("all", "live"):
            pools += [r for r in self.store.live_of_type(opp)]
        if scope in ("all", "dedup"):
            pools += [r for r in self.store.live_of_type(qtype)
                      if r.id != query.get("id")]
        return pools

    def match(self, query, scope: str = "all", top_k: int = 10,
              min_score: float = config.SHOW) -> list[dict]:
        query = _as_dict(query)
        results = []
        for cand in self._pool(query, scope):
            res = score_pair(query, cand, self.geo)
            if res["score"] >= min_score:
                results.append(res)
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
