"""Fast reunification matcher.

Re-implements the admin Jaccard matcher but cached + candidate-blocked so a query
scores only a small candidate set instead of scanning all ~2350 active cases and
re-tokenising every row on every request (the slow path called out in the audit).

  build_index()  — cached: tokenises every Active case ONCE (st.cache_resource)
  search(...)    — blocks candidates by gender/age/zone, then scores the rest
"""
from __future__ import annotations

import re

import streamlit as st

from . import data

_STOP = {"in", "a", "the", "with", "has", "near", "of", "and", "man", "woman",
         "wearing", "was", "is", "are", "for", "on", "at", "to"}

try:
    from rapidfuzz import fuzz
    _HAVE_FUZZ = True
except Exception:  # pragma: no cover
    _HAVE_FUZZ = False


def tokens(*parts: str | None) -> set[str]:
    text = " ".join(p for p in parts if p).lower()
    return {w for w in re.findall(r"[a-z0-9]+", text) if w not in _STOP and len(w) > 2}


@st.cache_resource(show_spinner="Building match index…")
def build_index() -> dict:
    """Tokenise all Active cases once. Returns parallel lists for fast scoring."""
    df = data.load_cases_df()
    active = df[df["status"] == "Active"].fillna("")
    idx = {
        "case_id": active["case_id"].tolist(),
        "name": active["name"].tolist(),
        "gender": active["gender"].tolist(),
        "age_band": active["age_band"].tolist(),
        "zone": active["zone"].tolist(),
        "language": active["language"].tolist(),
        "last_seen_location": active["last_seen_location"].tolist(),
        "physical_description": active["physical_description"].tolist(),
        "lat": active["lat"].tolist(),
        "lng": active["lng"].tolist(),
    }
    idx["tokens"] = [
        tokens(n, d, loc)
        for n, d, loc in zip(idx["name"], idx["physical_description"], idx["last_seen_location"])
    ]
    return idx


def search(
    *, query_text: str = "", name: str = "", gender: str = "", age_band: str = "",
    zone: str = "", location: str = "", top_n: int = 10,
) -> list[dict]:
    idx = build_index()
    q_tokens = tokens(query_text, name, location)
    n = len(idx["case_id"])

    results = []
    for i in range(n):
        # --- candidate blocking: cheap hard filters before scoring -----------
        if gender and idx["gender"][i] and idx["gender"][i] != gender:
            continue
        if age_band and idx["age_band"][i] and idx["age_band"][i] != age_band:
            continue
        if zone and idx["zone"][i] and idx["zone"][i] != zone:
            continue

        case_tokens = idx["tokens"][i]
        overlap = len(q_tokens & case_tokens)
        denom = len(q_tokens | case_tokens) or 1
        score = overlap / denom

        reasons = []
        if overlap:
            reasons.append(f"{overlap} shared term{'s' if overlap != 1 else ''}")

        # fuzzy name similarity (rapidfuzz if present, else a light fallback)
        if name and idx["name"][i]:
            if _HAVE_FUZZ:
                nr = fuzz.token_sort_ratio(name.lower(), idx["name"][i].lower()) / 100.0
            else:
                a, b = set(name.lower().split()), set(idx["name"][i].lower().split())
                nr = len(a & b) / (len(a | b) or 1)
            if nr > 0.55:
                score += 0.30 * nr
                reasons.append(f"name ~{int(nr * 100)}%")

        if gender and idx["gender"][i] == gender:
            score += 0.15
            reasons.append("same gender")
        if age_band and idx["age_band"][i] == age_band:
            score += 0.15
            reasons.append("same age band")
        if zone and idx["zone"][i] == zone:
            score += 0.20
            reasons.append("same zone")

        if score <= 0:
            continue
        results.append({
            "case_id": idx["case_id"][i],
            "name": idx["name"][i],
            "gender": idx["gender"][i],
            "age_band": idx["age_band"][i],
            "zone": idx["zone"][i],
            "language": idx["language"][i],
            "last_seen_location": idx["last_seen_location"][i],
            "physical_description": idx["physical_description"][i],
            "lat": idx["lat"][i],
            "lng": idx["lng"][i],
            "score": round(min(score, 1.0), 3),
            "reason": ", ".join(reasons) or "weak text overlap",
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]
