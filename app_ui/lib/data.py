"""Registry data layer for the Streamlit app.

Talks DIRECTLY to the seeded SQLite registry (backend/data/sangam.db) so we do
not depend on backend/shared (which collides with the repo-root `shared` package
the sim/planning code needs). Reads are cached; writes clear the relevant cache.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
DB_PATH = BACKEND / "data" / "sangam.db"
PHOTOS_DIR = BACKEND / "data" / "photos"
CSV_PATH = REPO_ROOT / "data" / "data" / "Synthetic_Missing_Persons_2500.csv"

# Demo staff so submission reviews have a valid reviewed_by FK.
SEED_STAFF = [
    ("admin", "admin", "Control Room Admin"),       # (username, role, name)
    ("operator", "operator", "Field Operator"),
]

_DDL = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY, type TEXT DEFAULT 'missing', name TEXT,
    name_normalized TEXT DEFAULT '', gender TEXT, age_band TEXT, language TEXT,
    state TEXT, district TEXT, last_seen_location TEXT, lat REAL, lng REAL,
    zone TEXT, reporting_center TEXT, reporter_mobile TEXT, physical_description TEXT,
    photo_path TEXT, audio_path TEXT, transcript TEXT, transcript_en TEXT,
    face_embedding TEXT, status TEXT DEFAULT 'Active', reported_at TEXT DEFAULT '',
    remarks TEXT
);
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('operator','admin')),
    name TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, missing_name TEXT, gender TEXT,
    age_band TEXT, last_seen_location TEXT, physical_description TEXT, photo_path TEXT,
    reporter_name TEXT, reporter_phone TEXT NOT NULL, lat REAL, lng REAL, zone TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(review_status IN ('pending','reviewing','matched','promoted','rejected')),
    reviewed_by INTEGER REFERENCES staff(id), reviewed_at TEXT, decision_note TEXT,
    matched_case_id TEXT REFERENCES cases(case_id),
    created_case_id TEXT REFERENCES cases(case_id), source_ip TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
-- Indexes that turn list/search full-scans into index lookups (perf).
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_zone ON cases(zone);
CREATE INDEX IF NOT EXISTS idx_cases_gender_age ON cases(gender, age_band);
CREATE INDEX IF NOT EXISTS idx_sub_review ON submissions(review_status);
"""


# --------------------------------------------------------------------------- #
# geo (self-contained file in backend/shared — no relative imports, importlib-safe)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _geo():
    spec = importlib.util.spec_from_file_location("sangam_geo", BACKEND / "shared" / "geo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=4096)
def resolve_location(loc: str | None):
    """(lat, lng, zone) for a free-text location; memoized."""
    return _geo().resolve(loc)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------------------------------- #
# Bootstrapping (create + seed if a fresh clone has no DB)
# --------------------------------------------------------------------------- #
def ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(_DDL)
        conn.commit()
        if not conn.execute("SELECT 1 FROM cases LIMIT 1").fetchone():
            _seed_cases(conn)
        if not conn.execute("SELECT 1 FROM staff LIMIT 1").fetchone():
            _seed_staff(conn)
    finally:
        conn.close()


def _seed_cases(conn: sqlite3.Connection) -> None:
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    rows = []
    for r in df.to_dict("records"):
        name = (r.get("missing_person_name") or "").strip() or None
        loc = (r.get("last_seen_location") or "").strip() or None
        lat, lng, zone = resolve_location(loc)
        status = "Reunited" if (r.get("status") or "").strip() == "Reunited" else "Active"
        rows.append((
            r["case_id"], "missing", name, (name or "").lower().strip(),
            r.get("gender") or None, r.get("age_band") or None, r.get("language") or None,
            r.get("state") or None, r.get("district") or None, loc, lat, lng, zone,
            r.get("reporting_center") or None, r.get("reporter_mobile") or None,
            r.get("physical_description") or None, status, r.get("reported_at") or "",
            r.get("remarks") or None,
        ))
    conn.executemany(
        """INSERT INTO cases (case_id, type, name, name_normalized, gender, age_band,
           language, state, district, last_seen_location, lat, lng, zone,
           reporting_center, reporter_mobile, physical_description, status,
           reported_at, remarks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


def _seed_staff(conn: sqlite3.Connection) -> None:
    try:
        from passlib.hash import bcrypt
        h = lambda p: bcrypt.hash(p)            # noqa: E731
    except Exception:
        h = lambda p: "plain:" + p              # noqa: E731 — demo fallback
    for username, role, name in SEED_STAFF:
        conn.execute(
            "INSERT OR IGNORE INTO staff (username, password_hash, role, name) VALUES (?,?,?,?)",
            (username, h(username + "123"), role, name),
        )
    conn.commit()


def staff_id_for_role(role: str) -> int | None:
    """Map the Streamlit role selector to a seeded staff row for reviewed_by."""
    conn = get_conn()
    try:
        want = "admin" if role.lower() == "admin" else "operator"
        row = conn.execute("SELECT id FROM staff WHERE role = ? ORDER BY id LIMIT 1", (want,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Cached reads
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_cases_df() -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql_query("SELECT * FROM cases", conn)
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def load_submissions_df() -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql_query("SELECT * FROM submissions ORDER BY created_at DESC, id DESC", conn)
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def analytics() -> dict:
    df = load_cases_df()
    subs = load_submissions_df()
    by_status = df["status"].value_counts().to_dict()
    top_zones = (
        df[df["status"] == "Active"]["zone"].dropna().value_counts().head(8).to_dict()
    )
    return {
        "total_cases": int(len(df)),
        "active": int((df["status"] == "Active").sum()),
        "reunited": int((df["status"] == "Reunited").sum()),
        "matched": int((df["status"] == "Matched").sum()),
        "by_status": by_status,
        "top_zones": top_zones,
        "pending_submissions": int((subs["review_status"] == "pending").sum()) if len(subs) else 0,
        "total_submissions": int(len(subs)),
    }


def _bust():
    """Invalidate cached reads after a write."""
    load_cases_df.clear()
    load_submissions_df.clear()
    analytics.clear()
    # match index depends on cases — clear it too (imported lazily to avoid a cycle)
    try:
        from . import matching
        matching.build_index.clear()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
def insert_submission(
    *, missing_name, gender, age_band, last_seen_location, physical_description,
    reporter_name, reporter_phone, photo_path=None, source="streamlit",
) -> int:
    lat, lng, zone = resolve_location(last_seen_location)
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO submissions (missing_name, gender, age_band, last_seen_location,
               physical_description, photo_path, reporter_name, reporter_phone, lat, lng,
               zone, review_status, source_ip)
               VALUES (?,?,?,?,?,?,?,?,?,?,?, 'pending', ?)""",
            (missing_name or None, gender or None, age_band or None,
             last_seen_location or None, physical_description or None, photo_path,
             reporter_name or None, reporter_phone, lat, lng, zone, source),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    _bust()
    return new_id


def set_reviewing(sub_id: int, staff_id: int | None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE submissions SET review_status='reviewing', reviewed_by=?, reviewed_at=? "
            "WHERE id=? AND review_status='pending'",
            (staff_id, now_iso(), sub_id),
        )
        conn.commit()
    finally:
        conn.close()
    _bust()


def confirm_match(sub_id: int, case_id: str, staff_id: int | None, note: str | None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE submissions SET review_status='matched', matched_case_id=?, reviewed_by=?, "
            "reviewed_at=?, decision_note=? WHERE id=?",
            (case_id, staff_id, now_iso(), note, sub_id),
        )
        conn.execute("UPDATE cases SET status='Matched' WHERE case_id=?", (case_id,))
        conn.commit()
    finally:
        conn.close()
    _bust()


def reject_submission(sub_id: int, staff_id: int | None, note: str | None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE submissions SET review_status='rejected', reviewed_by=?, reviewed_at=?, "
            "decision_note=? WHERE id=?",
            (staff_id, now_iso(), note, sub_id),
        )
        conn.commit()
    finally:
        conn.close()
    _bust()


def promote_submission(sub_id: int, staff_id: int | None) -> str:
    """Create a new PUB-NNNNN case from a submission (a found/new person)."""
    conn = get_conn()
    try:
        sub = conn.execute("SELECT * FROM submissions WHERE id=?", (sub_id,)).fetchone()
        if not sub:
            raise ValueError("submission not found")
        n = conn.execute("SELECT COUNT(*) FROM cases WHERE case_id LIKE 'PUB-%'").fetchone()[0]
        case_id = f"PUB-{n + 1:05d}"
        name = sub["missing_name"]
        conn.execute(
            """INSERT OR REPLACE INTO cases (case_id, type, name, name_normalized, gender,
               age_band, last_seen_location, lat, lng, zone, physical_description,
               photo_path, status, reported_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'Active', ?)""",
            (case_id, "found", name, (name or "").lower().strip(), sub["gender"],
             sub["age_band"], sub["last_seen_location"], sub["lat"], sub["lng"], sub["zone"],
             sub["physical_description"], sub["photo_path"], now_iso()),
        )
        conn.execute(
            "UPDATE submissions SET review_status='promoted', created_case_id=?, reviewed_by=?, "
            "reviewed_at=? WHERE id=?",
            (case_id, staff_id, now_iso(), sub_id),
        )
        conn.commit()
    finally:
        conn.close()
    _bust()
    return case_id


def reunite_case(case_id: str) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE cases SET status='Reunited' WHERE case_id=?", (case_id,))
        conn.commit()
    finally:
        conn.close()
    _bust()


# --------------------------------------------------------------------------- #
# Geo reference data (CCTV / police / chokepoints / zones) for the dashboard map
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def geo_reference() -> dict[str, pd.DataFrame]:
    from shared import loaders  # repo-root shared (sim/planning loaders)
    cams = pd.DataFrame([{"id": c.camera_id, "zone": c.zone, "lat": c.lat, "lon": c.lng}
                         for c in loaders.load_cameras()])
    police = pd.DataFrame([{"name": p.name, "lat": p.lat, "lon": p.lng}
                           for p in loaders.load_police_stations()])
    chokes = pd.DataFrame([{"name": c.name, "category": c.category, "lat": c.lat, "lon": c.lng}
                           for c in loaders.load_chokepoints()])
    zones = pd.DataFrame([{"name": z.name, "lat": z.lat, "lon": z.lng, "pts": z.boundary_points}
                          for z in loaders.load_zones()])
    return {"cameras": cams, "police": police, "chokepoints": chokes, "zones": zones}
