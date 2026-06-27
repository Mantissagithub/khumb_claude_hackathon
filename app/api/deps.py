"""
Shared dependencies for the API layer.

Settings come from config/secrets.toml via config.load_secrets() — the same
single source of truth the Streamlit admin uses, so the API and the dashboard
stay in sync. The store is cached per (url, key) so we don't rebuild a Supabase
client on every request.
"""

from config import load_secrets

_DEFAULT_MODEL = "claude-opus-4-8"
_store_cache: dict = {}


def get_settings() -> dict:
    """Resolved runtime settings, read fresh each call (the file is tiny)."""
    s = load_secrets()
    return {
        "claude_key": s["anthropic"]["api_key"] or None,
        "claude_model": s["anthropic"]["model"] or _DEFAULT_MODEL,
        "supabase_url": s["supabase"]["url"] or None,
        "supabase_key": s["supabase"]["anon_key"] or None,
    }


def get_store_bundle():
    """Return (store, mode, error), cached by credentials.

    Importing get_store here (not at module top) keeps optional deps lazy.
    """
    from app.services.store import get_store

    cfg = get_settings()
    cache_key = (cfg["supabase_url"], cfg["supabase_key"])
    if cache_key not in _store_cache:
        _store_cache[cache_key] = get_store(cfg["supabase_url"], cfg["supabase_key"])
    return _store_cache[cache_key]


def get_store():
    """FastAPI dependency: just the store object."""
    return get_store_bundle()[0]
