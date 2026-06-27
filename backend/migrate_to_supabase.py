"""One-shot: push the locally-seeded cases from sangam.db into Supabase.

Signs in as the seeded admin so inserts satisfy the `cases_insert_auth` RLS
policy (authenticated). Idempotent via upsert on case_id.
"""

from __future__ import annotations

import os
import sqlite3

from supabase import create_client

SUPABASE_URL = "https://cpbmfnjeqtnjzeoogpoo.supabase.co"
SUPABASE_KEY = "sb_publishable_BAZV-UJzryDm396f1i3FAg_54287XrC"
ADMIN_EMAIL = "admin@sangam.local"
ADMIN_PASS = "admin123"

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "data", "sangam.db")

COLS = [
    "case_id", "type", "name", "name_normalized", "gender", "age_band", "language",
    "state", "district", "last_seen_location", "lat", "lng", "zone",
    "reporting_center", "reporter_mobile", "physical_description", "photo_path",
    "audio_path", "transcript", "transcript_en", "status", "reported_at", "remarks",
]


def main() -> None:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    sb.auth.sign_in_with_password({"email": ADMIN_EMAIL, "password": ADMIN_PASS})

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT {', '.join(COLS)} FROM cases").fetchall()
    conn.close()

    records = [{k: r[k] for k in COLS} for r in rows]
    print(f"Read {len(records)} cases from sqlite")

    batch = 500
    for i in range(0, len(records), batch):
        chunk = records[i : i + batch]
        sb.table("cases").upsert(chunk, on_conflict="case_id").execute()
        print(f"  upserted {i + len(chunk)}/{len(records)}")

    print("done")


if __name__ == "__main__":
    main()
