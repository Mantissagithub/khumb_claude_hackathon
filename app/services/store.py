"""
Pluggable ticket store.

- `SupabaseStore` — live Postgres via Supabase, used when a URL + anon key are
  provided in the UI. `supabase` is imported lazily so the app runs without it.
- `LocalStore` — a JSON file, used as the default/fallback so the demo works
  with zero setup.

Both expose the same three methods, and tickets are plain dicts whose keys match
the Supabase table columns (see SQL in README / the Streamlit sidebar), so the
same record inserts cleanly into either backend.
"""

import json
import os
from threading import Lock

_lock = Lock()


class LocalStore:
    def __init__(self, path: str = "data/streamlit_ledger.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump([], f)

    def _read(self) -> list[dict]:
        with open(self.path) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _write(self, rows: list[dict]) -> None:
        with open(self.path, "w") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

    def list_tickets(self) -> list[dict]:
        rows = self._read()
        return sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)

    def add_ticket(self, ticket: dict) -> dict:
        with _lock:
            rows = self._read()
            rows.append(ticket)
            self._write(rows)
        return ticket

    def update_ticket(self, ticket_id: str, fields: dict) -> None:
        with _lock:
            rows = self._read()
            for r in rows:
                if r.get("ticket_id") == ticket_id:
                    r.update(fields)
            self._write(rows)


class SupabaseStore:
    def __init__(self, url: str, key: str, table: str = "tickets"):
        from supabase import create_client  # lazy import

        self.client = create_client(url, key)
        self.table = table

    def list_tickets(self) -> list[dict]:
        resp = (
            self.client.table(self.table)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data or []

    def add_ticket(self, ticket: dict) -> dict:
        self.client.table(self.table).insert(ticket).execute()
        return ticket

    def update_ticket(self, ticket_id: str, fields: dict) -> None:
        self.client.table(self.table).update(fields).eq("ticket_id", ticket_id).execute()


def get_store(supabase_url: str | None, supabase_key: str | None):
    """Return a SupabaseStore if creds are given and the lib is installed,
    else a LocalStore. Returns (store, mode, error)."""
    if supabase_url and supabase_key:
        try:
            return SupabaseStore(supabase_url, supabase_key), "supabase", None
        except Exception as exc:  # noqa: BLE001
            return LocalStore(), "local", str(exc)
    return LocalStore(), "local", None


# The SQL to create the matching Supabase table.
SUPABASE_SCHEMA_SQL = """\
create table if not exists tickets (
  ticket_id text primary key,
  description text,
  summary text,
  language text,
  department text,
  priority text,
  confidence float8,
  reasoning text,
  recommended_action text,
  nearest_asset text,
  tags jsonb,
  status text default 'NEW',
  dispatch_stage int default 0,
  assigned_department text,
  zone text,
  latitude float8,
  longitude float8,
  photo_b64 text,
  reporter_name text,
  reporter_contact text,
  ai_engine text,
  created_at timestamptz default now(),
  assigned_at timestamptz
);
"""
