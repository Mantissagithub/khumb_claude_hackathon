"""SQLite layer: schema, connection, and idempotent seeding.

Tables:
  - cases        : canonical registry, seeded from the 2500-row CSV
  - staff        : auth accounts (operator | admin), seeded with demo creds
  - submissions  : untrusted public inbox awaiting operator review

`init_db()` is called once on startup (FastAPI lifespan) and is safe to re-run.
"""

from __future__ import annotations

import os
import sqlite3

import pandas as pd

from . import geo
from .security import hash_password

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
_REPO = os.path.dirname(_BACKEND)

DB_PATH = os.path.join(_BACKEND, "data", "sangam.db")
CSV_PATH = os.path.join(_REPO, "data", "data", "Synthetic_Missing_Persons_2500.csv")
PHOTOS_DIR = os.path.join(_BACKEND, "data", "photos")

# Demo staff accounts (documented in README). Seeded only if the table is empty.
SEED_STAFF = [
    ("admin", "admin123", "admin", "Control Room Admin"),
    ("operator", "operator123", "operator", "Field Operator"),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            type TEXT DEFAULT 'missing',
            name TEXT,
            name_normalized TEXT DEFAULT '',
            gender TEXT,
            age_band TEXT,
            language TEXT,
            state TEXT,
            district TEXT,
            last_seen_location TEXT,
            lat REAL,
            lng REAL,
            zone TEXT,
            reporting_center TEXT,
            reporter_mobile TEXT,
            physical_description TEXT,
            photo_path TEXT,
            audio_path TEXT,
            transcript TEXT,
            transcript_en TEXT,
            face_embedding TEXT,
            status TEXT DEFAULT 'Active',
            reported_at TEXT DEFAULT '',
            remarks TEXT
        );

        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('operator','admin')),
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            missing_name TEXT,
            gender TEXT,
            age_band TEXT,
            last_seen_location TEXT,
            physical_description TEXT,
            photo_path TEXT,
            reporter_name TEXT,
            reporter_phone TEXT NOT NULL,
            lat REAL,
            lng REAL,
            zone TEXT,
            review_status TEXT NOT NULL DEFAULT 'pending'
                CHECK(review_status IN ('pending','reviewing','matched','promoted','rejected')),
            reviewed_by INTEGER REFERENCES staff(id),
            reviewed_at TEXT,
            decision_note TEXT,
            matched_case_id TEXT REFERENCES cases(case_id),
            created_case_id TEXT REFERENCES cases(case_id),
            source_ip TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()


def _seed_cases(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM cases LIMIT 1").fetchone():
        return
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    rows = []
    for r in df.to_dict("records"):
        name = (r.get("missing_person_name") or "").strip() or None
        loc = (r.get("last_seen_location") or "").strip() or None
        lat, lng, zone = geo.resolve(loc)
        csv_status = (r.get("status") or "").strip()
        status = "Reunited" if csv_status == "Reunited" else "Active"
        rows.append((
            r["case_id"], "missing", name, (name or "").lower().strip(),
            r.get("gender") or None, r.get("age_band") or None, r.get("language") or None,
            r.get("state") or None, r.get("district") or None, loc, lat, lng, zone,
            r.get("reporting_center") or None, r.get("reporter_mobile") or None,
            r.get("physical_description") or None, status, r.get("reported_at") or "",
            r.get("remarks") or None,
        ))
    conn.executemany(
        """INSERT INTO cases
           (case_id, type, name, name_normalized, gender, age_band, language,
            state, district, last_seen_location, lat, lng, zone,
            reporting_center, reporter_mobile, physical_description,
            status, reported_at, remarks)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


def _seed_staff(conn: sqlite3.Connection) -> None:
    for username, password, role, name in SEED_STAFF:
        conn.execute(
            "INSERT OR IGNORE INTO staff (username, password_hash, role, name) VALUES (?,?,?,?)",
            (username, hash_password(password), role, name),
        )
    conn.commit()


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    conn = get_conn()
    try:
        _create_tables(conn)
        _seed_cases(conn)
        _seed_staff(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    c = get_conn()
    print("cases:", c.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
    print("staff:", c.execute("SELECT username, role FROM staff").fetchall())
    print("submissions:", c.execute("SELECT COUNT(*) FROM submissions").fetchone()[0])
    c.close()
