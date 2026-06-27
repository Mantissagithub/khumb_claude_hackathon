"""Smoke test: exercises the core pipeline with NO ML deps required.

Run from the backend/ directory:  python scripts/smoke_test.py

Verifies: CSV loading, geo enrichment, gazetteer resolution, the fusion
engine (text+geo+demographics+cloth-from-text), dedup, and the voice query
parser — all without face_recognition / whisper / numpy installed.
"""
import os
import sys

# make `app` importable when run as a plain script from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import data_loader            # noqa: E402
from app.matching import text as T     # noqa: E402
from app.matching import voice         # noqa: E402
from app.matching.engine import MatchEngine  # noqa: E402
from app.store import Store            # noqa: E402


def main() -> None:
    geo = data_loader.GeoContext.build()
    gov = data_loader.load_government_registry()
    store = Store(gov)
    engine = MatchEngine(store, geo)
    print(f"[load] zones={len(geo.zones)} cctv={len(geo.cctv)} "
          f"police={len(geo.police)} chokepoints={len(geo.chokepoints)} "
          f"registry={len(gov)}")

    # pick a real registry row to match against
    ref = next(r for r in gov if r["name"] and r["reporter_mobile"])
    print(f"[ref ] {ref['case_id']} {ref['name']} | {ref['last_seen_location']}")

    # a FOUND report describing that same person (volunteer + fetched ID)
    query = {
        "type": "found",
        "name": ref["name"],
        "gender": ref["gender"],
        "age_band": ref["age_band"],
        "state": ref["state"],
        "district": ref["district"],
        "language": ref["language"],
        "last_seen_location": ref["last_seen_location"],
        "reporter_mobile": ref["reporter_mobile"],
        "physical_description": ref["physical_description"],
    }
    matches = engine.match(query, scope="all", top_k=3)
    print(f"[match] {len(matches)} candidates")
    top = matches[0]
    print(f"   #1 -> {top['candidate_id']} score={top['score']} "
          f"decision={top['decision']}")
    print(f"        reasons: {top['reasons']}")
    print(f"        location: zone={top['location'].get('zone')} "
          f"police={top['location'].get('nearest_police')} "
          f"cctv_nearby={top['location'].get('cctv_nearby')}")
    assert top["candidate_id"] == ref["case_id"], "top match should be the ref row"
    assert top["score"] >= 0.7, "exact-ish duplicate should score high"

    # appearance extraction (cloth-from-text, multilingual)
    app = T.extract_appearance("budhi aurat, lal saree, has rudraksha mala")
    print(f"[cloth] {app}")
    assert "red" in app["colors"] and "saree" in app["garments"]

    # voice query parser (no audio, just the text path)
    vq = voice.parse_query("an old woman in a red saree near Trimbakeshwar")
    print(f"[voice] gender={vq['gender']} age={vq['age_band']} "
          f"colors={vq['appearance']['colors']}")
    assert vq["gender"] == "Female"

    print("\nALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
