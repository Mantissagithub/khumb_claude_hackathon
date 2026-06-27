"""
KumbhSeva — Admin Control Room (handover module).

This is the ADMIN side only. Citizen reports are captured elsewhere (the main
application) and written to a shared Supabase `tickets` table. This module:

  1. Connects to Supabase (URL + anon key in the sidebar) and fetches tickets
     live — new citizen uploads appear here on refresh / auto-refresh.
  2. Enriches any raw ticket that has no AI suggestion yet by running Claude
     triage on the admin side, and writes the result back to Supabase (so it is
     computed once). Works with or without the capture side doing any AI.
  3. Lets the admin open a full case, see the AI department suggestion, the three
     responder centres (nearest centre name / code / distance), and drive a live
     dispatch roadmap: Reported -> Dispatched -> En route -> On-site -> Resolved.

Integration boundary = the Supabase `tickets` table (schema in the sidebar /
HANDOVER.md). Portable logic lives in app/services/*; this file is the reference
admin UI.

Run:  streamlit run streamlit_app.py
"""

import base64
import time
import uuid
from datetime import datetime, timezone

import streamlit as st

from app.services import triage
from app.services.knowledge_graph import nearest_asset_detail
from app.services.store import SUPABASE_SCHEMA_SQL, get_store
from app.services.triage import RESPONDERS
from config import load_secrets

st.set_page_config(page_title="KumbhSeva — Admin Control Room", page_icon="🕉️",
                   layout="wide")

PRIORITY_COLOR = {"CRITICAL": "#ff5a5a", "HIGH": "#ff9f43",
                  "MEDIUM": "#54a0ff", "LOW": "#8395a7"}
STAGES = ["Reported", "Dispatched", "En route", "On-site", "Resolved"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_photo(container, ticket) -> None:
    """Show a ticket photo from a URL or base64 payload, if present."""
    if ticket.get("photo_url"):
        try:
            container.image(ticket["photo_url"], use_container_width=True)
            return
        except Exception:  # noqa: BLE001
            pass
    if ticket.get("photo_b64"):
        try:
            container.image(base64.b64decode(ticket["photo_b64"]), use_container_width=True)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# AI enrichment — run Claude triage on any ticket that has no suggestion yet,
# and persist it back to the store so it is computed only once.
# --------------------------------------------------------------------------- #
def _needs_enrichment(t: dict) -> bool:
    return not t.get("department") or not t.get("summary")


def enrich_tickets(store, tickets: list[dict], api_key: str, model: str) -> list[dict]:
    enriched = []
    for t in tickets:
        if _needs_enrichment(t):
            analysis, engine = triage.classify(
                description=t.get("description", ""), api_key=api_key or None,
                model=model, zone=t.get("zone"),
                lat=t.get("latitude"), lon=t.get("longitude"),
            )
            patch = {**analysis, "ai_engine": engine}
            if not t.get("status"):
                patch["status"] = "NEW"
            if t.get("dispatch_stage") is None:
                patch["dispatch_stage"] = 0
            try:
                store.update_ticket(t["ticket_id"], patch)
            except Exception as exc:  # noqa: BLE001
                print(f"[KumbhSeva] enrichment write-back failed for {t.get('ticket_id')}: {exc}")
            t = {**t, **patch}
        enriched.append(t)
    return enriched


# --------------------------------------------------------------------------- #
# Dispatch roadmap renderers (no emoji)
# --------------------------------------------------------------------------- #
def flow_html(active: int) -> str:
    css = """
    <style>
    @keyframes ksPulse {
      0%   { box-shadow: 0 0 0 0 rgba(210,153,34,.75); }
      70%  { box-shadow: 0 0 0 14px rgba(210,153,34,0); }
      100% { box-shadow: 0 0 0 0 rgba(210,153,34,0); }
    }
    .ks-pulse { animation: ksPulse 1.4s infinite; }
    </style>
    """
    parts = []
    for i, label in enumerate(STAGES):
        if i > 0:
            line = "#2ea043" if i <= active else "#30363d"
            parts.append(
                f'<div style="flex:1;height:3px;background:{line};margin-top:19px"></div>'
            )
        if i < active:
            nc, tc, cls, mark = "#2ea043", "#c9d1d9", "", "&#10003;"
        elif i == active:
            nc, tc, cls, mark = "#d29922", "#f0f6fc", "ks-pulse", str(i + 1)
        else:
            nc, tc, cls, mark = "#30363d", "#6e7681", "", str(i + 1)
        parts.append(
            f'<div style="display:flex;flex-direction:column;align-items:center;width:96px">'
            f'<div class="{cls}" style="width:40px;height:40px;border-radius:50%;'
            f'background:{nc};color:#0d1117;display:flex;align-items:center;'
            f'justify-content:center;font-weight:700;font-family:Helvetica,Arial,sans-serif">'
            f'{mark}</div>'
            f'<div style="margin-top:8px;font-size:12px;color:{tc};text-align:center;'
            f'font-family:Helvetica,Arial,sans-serif">{label}</div></div>'
        )
    return css + (
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        'padding:18px 6px;background:#0d1117;border:1px solid #30363d;border-radius:10px">'
        + "".join(parts)
        + "</div>"
    )


def roadmap_dot(active: int) -> str:
    nodes = []
    for i, label in enumerate(STAGES):
        if i < active:
            fill, fc = "#1b4332", "#7ee2a8"
        elif i == active:
            fill, fc = "#5c4413", "#ffd57a"
        else:
            fill, fc = "#161b22", "#6e7681"
        nodes.append(
            f'n{i}[label="{label}" fillcolor="{fill}" fontcolor="{fc}" color="#30363d"];'
        )
    edges = "->".join(f"n{i}" for i in range(len(STAGES))) + ";"
    return (
        'digraph {rankdir=LR;bgcolor="transparent";'
        'node[shape=box style="rounded,filled" fontname="Helvetica" fontsize=11];'
        'edge[color="#30363d"];' + "".join(nodes) + edges + "}"
    )


# --------------------------------------------------------------------------- #
# Sidebar — connections / settings
# --------------------------------------------------------------------------- #
def render_sidebar():
    # All keys come from the central store (config/secrets.toml) — no key inputs
    # in the UI. Fill them in that file (see config/secrets.toml.example).
    _secrets = load_secrets()
    supabase_url = _secrets["supabase"]["url"]
    supabase_key = _secrets["supabase"]["anon_key"]
    claude_key = _secrets["anthropic"]["api_key"]
    claude_model = _secrets["anthropic"]["model"] or "claude-opus-4-8"

    store, mode, store_err = get_store(supabase_url or None, supabase_key or None)

    # The sidebar holds ONLY the issue intake form.
    with st.sidebar:
        st.header("Raise an Issue")
        with st.form("raise_issue", clear_on_submit=True):
            description = st.text_area(
                "Describe the issue *",
                placeholder="Any language — e.g. 'My son is lost near Sangam Ghat'",
            )
            zone = st.text_input("Zone / landmark", placeholder="e.g. Sector 7")
            c1, c2 = st.columns(2)
            lat = c1.number_input("Latitude", value=25.4225, format="%.5f")
            lon = c2.number_input("Longitude", value=81.8836, format="%.5f")
            photo = st.file_uploader("Photo", type=["png", "jpg", "jpeg"])
            name = st.text_input("Reporter name", placeholder="optional")
            contact = st.text_input("Contact", placeholder="optional")
            submitted = st.form_submit_button("Submit issue", type="primary",
                                              use_container_width=True)
        if submitted:
            if not description.strip():
                st.warning("Please describe the issue.")
            else:
                photo_b64 = (
                    base64.b64encode(photo.getvalue()).decode("ascii") if photo else None
                )
                store.add_ticket({
                    "ticket_id": f"KS-{uuid.uuid4().hex[:8].upper()}",
                    "description": description.strip(), "zone": zone or None,
                    "latitude": lat, "longitude": lon, "photo_b64": photo_b64,
                    "reporter_name": name or None, "reporter_contact": contact or None,
                    "status": "NEW", "dispatch_stage": 0, "created_at": _now(),
                })
                st.session_state["view"] = "dashboard"
                st.rerun()

    return store, mode, claude_key, claude_model, store_err


# --------------------------------------------------------------------------- #
# DASHBOARD (admin-only)
# --------------------------------------------------------------------------- #
def _ticket_card(t: dict) -> None:
    dept_code = t.get("department")
    dept = RESPONDERS.get(dept_code, {"name": dept_code})
    prio = t.get("priority", "—")
    color = PRIORITY_COLOR.get(prio, "#8395a7")

    with st.container(border=True):
        top_l, top_r = st.columns([3, 1])
        top_l.markdown(f"**{t.get('summary') or t.get('description')}**")
        top_r.markdown(
            f"<span style='background:{color};color:#111;padding:2px 8px;"
            f"border-radius:10px;font-size:12px;font-weight:600'>{prio}</span>",
            unsafe_allow_html=True,
        )

        badges = [f"`{t['ticket_id']}`"]
        if t.get("zone"):
            badges.append(f" {t['zone']}")
        if t.get("language") and "english" not in str(t["language"]).lower():
            badges.append(f" {t['language']}")
        badges.append(f" {t.get('ai_engine', '?')}")
        st.caption(" · ".join(badges))

        cdesc, cimg = st.columns([2, 1])
        cdesc.write(t.get("description", ""))
        render_photo(cimg, t)

        st.markdown(
            f" **AI suggests → {dept.get('name', dept_code)}** "
            f"({round(float(t.get('confidence', 0)) * 100)}% confidence)"
        )
        st.caption(f"Why: {t.get('reasoning', '')}")
        if t.get("nearest_asset"):
            st.caption(f"🏥 Nearest asset: {t['nearest_asset']}")

        if st.button("View full case →", key=f"view_{t['ticket_id']}",
                     use_container_width=True):
            st.session_state["view"] = "detail"
            st.session_state["selected_ticket_id"] = t["ticket_id"]
            st.rerun()

        if t.get("status") in ("ASSIGNED", "RESOLVED"):
            ad = RESPONDERS.get(t.get("assigned_department"), {})
            label = "Resolved" if t.get("status") == "RESOLVED" else "Assigned"
            st.success(f"✓ {label} → {ad.get('name', t.get('assigned_department'))}")
        else:
            st.write("**Assign to:**")
            b1, b2, b3 = st.columns(3)
            for col, code in ((b1, "POLICE"), (b2, "MEDICAL"), (b3, "FIRE_BRIGADE")):
                if col.button(RESPONDERS[code]["name"],
                              key=f"assign_{code}_{t['ticket_id']}",
                              type="primary" if code == dept_code else "secondary",
                              use_container_width=True):
                    store_global.update_ticket(
                        t["ticket_id"],
                        {"assigned_department": code, "status": "ASSIGNED",
                         "assigned_at": _now(), "dispatch_stage": 1},
                    )
                    st.rerun()


def _dashboard_body(store, claude_key, claude_model) -> None:
    tickets = enrich_tickets(store, store.list_tickets(), claude_key, claude_model)
    open_count = sum(1 for t in tickets if t.get("status") == "NEW")
    st.caption(f"{len(tickets)} tickets · {open_count} unassigned")

    if not tickets:
        st.info("No tickets yet. Citizen reports arrive from Supabase (configure "
                "keys in config/secrets.toml), or raise one from the sidebar form.")
        return

    cols = st.columns(2, gap="medium")
    for i, t in enumerate(tickets):
        with cols[i % 2]:
            _ticket_card(t)


def render_dashboard(store, claude_key, claude_model, mode, store_err) -> None:
    h1, h2, h3 = st.columns([3, 1, 1])
    h1.title("KumbhSeva — Admin Control Room")
    if h2.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    auto = h3.checkbox("Auto (8s)", key="auto_refresh",
                       help="Re-fetch tickets from Supabase every 8 seconds.")

    storage = "Supabase (live)" if mode == "supabase" else "Local store (testing)"
    ai = ("Claude " + claude_model) if claude_key else "keyword fallback"
    st.caption(f"Storage: {storage} · AI routing: {ai}")
    if store_err:
        st.warning(f"Supabase connection failed, using local store: {store_err}")

    body = st.fragment(run_every="8s" if auto else None)(_dashboard_body)
    body(store, claude_key, claude_model)


# --------------------------------------------------------------------------- #
# CASE DETAIL (admin)
# --------------------------------------------------------------------------- #
def render_case_detail(store) -> None:
    ticket_id = st.session_state.get("selected_ticket_id")
    ticket = next(
        (t for t in store.list_tickets() if t.get("ticket_id") == ticket_id), None
    )

    hl, hr = st.columns([4, 1])
    if ticket is None:
        hl.title("Case not found")
        if hr.button("← Dashboard", use_container_width=True):
            st.session_state["view"] = "dashboard"
            st.rerun()
        return

    hl.title(f"Case {ticket['ticket_id']}")
    if hr.button("← Dashboard", use_container_width=True):
        st.session_state["view"] = "dashboard"
        st.rerun()

    stage = int(ticket.get("dispatch_stage") or 0)
    dept_code = ticket.get("department")
    dept = RESPONDERS.get(dept_code, {"name": dept_code})
    lat, lon, zone = ticket.get("latitude"), ticket.get("longitude"), ticket.get("zone")

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("Citizen Report")
        with st.container(border=True):
            st.markdown("**Full description**")
            st.write(ticket.get("description", ""))
            m1, m2 = st.columns(2)
            m1.markdown(f"**Reporter:** {ticket.get('reporter_name') or 'Anonymous'}")
            m2.markdown(f"**Contact:** {ticket.get('reporter_contact') or '—'}")
            m1.markdown(f"**Zone:** {zone or '—'}")
            m2.markdown(f"**Reported language:** {ticket.get('language') or '—'}")
            if lat is not None and lon is not None:
                st.markdown(f"**Location:** {lat:.5f}, {lon:.5f}")
                try:
                    st.map({"lat": [float(lat)], "lon": [float(lon)]}, size=40, zoom=13)
                except Exception:  # noqa: BLE001
                    pass
            if ticket.get("photo_url") or ticket.get("photo_b64"):
                st.markdown("**Attached photo**")
                render_photo(st, ticket)

        st.subheader("AI Summary")
        with st.container(border=True):
            st.markdown(f"**{ticket.get('summary', '')}**")
            st.write(ticket.get("reasoning", ""))
            st.markdown(f"**Recommended action:** {ticket.get('recommended_action', '')}")
            if ticket.get("tags"):
                st.caption("Tags: " + ", ".join(ticket["tags"]))
            st.caption(
                f"Priority {ticket.get('priority','—')} · "
                f"confidence {round(float(ticket.get('confidence',0))*100)}% · "
                f"engine {ticket.get('ai_engine','?')}"
            )

    with right:
        st.subheader("AI Department Suggestion")
        with st.container(border=True):
            st.markdown(f"### → {dept.get('name', dept_code)}")
            st.caption("Suggested responder, based on the report.")

        st.subheader("Responder Centres")
        for code in ("POLICE", "MEDICAL", "FIRE_BRIGADE"):
            meta = RESPONDERS[code]
            detail = nearest_asset_detail(code, lat, lon, zone)
            with st.container(border=True):
                title = meta["name"] + ("   ·   AI suggested" if code == dept_code else "")
                st.markdown(f"**{title}**")
                if detail:
                    dist = (f"{detail['distance_km']} km away"
                            if detail.get("distance_km") is not None else "distance unknown")
                    st.caption(f"Nearest centre: {detail['name']}  ({detail['code']}) — {dist}")
                else:
                    st.caption("No mapped centre.")

        st.subheader("Dispatch Roadmap")
        if not ticket.get("assigned_department"):
            st.write("Assign a responder to begin dispatch:")
            a1, a2, a3 = st.columns(3)
            for col, code in ((a1, "POLICE"), (a2, "MEDICAL"), (a3, "FIRE_BRIGADE")):
                if col.button(RESPONDERS[code]["name"], key=f"detail_assign_{code}",
                              type="primary" if code == dept_code else "secondary",
                              use_container_width=True):
                    store.update_ticket(
                        ticket_id,
                        {"assigned_department": code, "status": "ASSIGNED",
                         "assigned_at": _now(), "dispatch_stage": 1},
                    )
                    st.rerun()

        flow_ph = st.empty()
        flow_ph.markdown(flow_html(stage), unsafe_allow_html=True)
        st.graphviz_chart(roadmap_dot(stage), use_container_width=True)

        assigned = ticket.get("assigned_department")
        if assigned:
            ad = RESPONDERS.get(assigned, {})
            c1, c2 = st.columns(2)
            run = c1.button("Run live dispatch", type="primary", use_container_width=True,
                            disabled=stage >= len(STAGES) - 1)
            if c2.button("Reset roadmap", use_container_width=True):
                store.update_ticket(ticket_id, {"dispatch_stage": 1, "status": "ASSIGNED"})
                st.rerun()

            if run:
                for s in range(max(stage + 1, 1), len(STAGES)):
                    flow_ph.markdown(flow_html(s), unsafe_allow_html=True)
                    time.sleep(0.9)
                store.update_ticket(
                    ticket_id, {"dispatch_stage": len(STAGES) - 1, "status": "RESOLVED"}
                )
                centre = (nearest_asset_detail(assigned, lat, lon, zone) or {}).get(
                    "name", "centre")
                st.success(f"{ad.get('name', assigned)} dispatched from {centre} — case resolved.")
                time.sleep(0.6)
                st.rerun()

            if stage >= len(STAGES) - 1:
                st.success("Case resolved.")


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
store_global, mode, claude_key, claude_model, store_err = render_sidebar()

if st.session_state.get("view") == "detail":
    render_case_detail(store_global)
else:
    render_dashboard(store_global, claude_key, claude_model, mode, store_err)
