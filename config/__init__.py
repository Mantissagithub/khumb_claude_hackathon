"""
Central API-key store.

All secrets (Claude + Supabase) live in config/secrets.toml (gitignored).
`load_secrets()` reads them with safe defaults so the app runs even if the file
is missing or partial. The admin UI uses these as the pre-filled defaults for
its sidebar, and you can still override them at runtime.
"""

import pathlib
import tomllib

_SECRETS_PATH = pathlib.Path(__file__).parent / "secrets.toml"

_DEFAULTS = {
    "anthropic": {"api_key": "", "model": "claude-opus-4-8"},
    "supabase": {"url": "", "anon_key": ""},
}


def load_secrets() -> dict:
    """Return {'anthropic': {...}, 'supabase': {...}} merged over defaults."""
    if not _SECRETS_PATH.exists():
        return {k: dict(v) for k, v in _DEFAULTS.items()}
    try:
        with open(_SECRETS_PATH, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:  # noqa: BLE001
        print(f"[KumbhSeva] could not read config/secrets.toml: {exc}")
        return {k: dict(v) for k, v in _DEFAULTS.items()}
    return {
        "anthropic": {**_DEFAULTS["anthropic"], **data.get("anthropic", {})},
        "supabase": {**_DEFAULTS["supabase"], **data.get("supabase", {})},
    }
