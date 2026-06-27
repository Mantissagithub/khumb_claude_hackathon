"""
TEST DATA — DELETE THIS FILE once you've verified the logic works.

Posts a batch of sample devotee reports to the running API so you can see the
admin dashboard populate with AI-routed tickets. Includes:
  - multilingual reports (Marathi / Telugu / Hindi) to test translation
  - several near-identical "broken barricade in Zone 2" reports to test
    duplicate detection / auto-merge + escalation
  - location-specific reports to test knowledge-graph asset linking

Usage:
    1. Start the server:   uvicorn app.main:app --reload
    2. In another terminal: python data/seed_issues.py
    3. Open http://localhost:8000/admin
"""

import json
import urllib.request

API = "http://localhost:8000/api/v1/issues"

SAMPLE_ISSUES = [
    # Lost person — English, with location for asset linking
    {"description": "My 6-year-old son got separated from me in the crowd. He is "
     "wearing a red shirt.", "zone": "Sangam Ghat", "reporter_name": "Ramesh"},

    # Medical — Hindi
    {"description": "एक बुजुर्ग आदमी बेहोश होकर गिर गया है, उसे साँस लेने में दिक्कत हो रही है।",
     "zone": "Sector 7", "reporter_name": "Volunteer Sunita"},

    # Theft — Marathi (tests translation)
    {"description": "माझा मोबाईल आणि पैशाचे पाकीट कोणीतरी चोरले आहे, गर्दीत खिसा कापला.",
     "zone": "Sector 4", "reporter_name": "Anil"},

    # Fire hazard — Telugu (tests translation + CRITICAL priority)
    {"description": "ఒక ఫుడ్ స్టాల్ దగ్గర గ్యాస్ సిలిండర్ నుండి మంటలు వస్తున్నాయి, పొగ చాలా ఉంది.",
     "zone": "Mela Bazaar", "reporter_name": "Lakshmi"},

    # Crowd / stampede risk
    {"description": "Huge dangerous crowd crush building up on the bridge, people "
     "are getting pushed and could fall.", "zone": "Ram Ghat Bridge"},

    # ---- Duplicate cluster: broken barricade in Zone 2 (should auto-merge) ----
    {"description": "The metal barricade near the entrance of Sector 2 is broken "
     "and people are spilling onto the road.", "zone": "Sector 2", "reporter_name": "A"},
    {"description": "Barricade in sector 2 is broken, crowd pushing through the gap.",
     "zone": "Sector 2", "reporter_name": "B"},
    {"description": "Broken barricade at sector 2 gate, it is unsafe.",
     "zone": "Sector 2", "reporter_name": "C"},
    {"description": "The fencing/barricade at the Sector 2 entry has collapsed.",
     "zone": "Sector 2", "reporter_name": "D"},

    # Sanitation — routine
    {"description": "Toilets near sector 7 camp are overflowing and very dirty.",
     "zone": "Sector 7"},

    # General query
    {"description": "What time does the main aarti start this evening?",
     "zone": "Main Gate"},
]


def post(issue: dict) -> None:
    data = json.dumps(issue).encode("utf-8")
    req = urllib.request.Request(
        API, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    ai = body["ticket"].get("ai_analysis") or {}
    tag = "MERGED →" if body["merged"] else "NEW    →"
    print(f"{tag} {body['ticket']['ticket_id']} | "
          f"{ai.get('suggested_department','?'):16} | {ai.get('priority','?'):8} | "
          f"{ai.get('language','?'):12} | {ai.get('summary','')[:45]}")


if __name__ == "__main__":
    print("Seeding sample issues into KumbhSeva...\n")
    for issue in SAMPLE_ISSUES:
        try:
            post(issue)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! failed: {exc} (is the server running on :8000?)")
            break
    print("\nDone. Open http://localhost:8000/admin")
