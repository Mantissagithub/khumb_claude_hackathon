"""Download REAL test data for the matching demo (faces + crowd/clothing).

  faces/  -> LFW images: same person has _0001/_0002 etc. -> lets us verify
             that same-person distance < different-person distance.
  crowd/  -> real Kumbh / Indian-attire photos from Wikimedia Commons, for
             the cloth colour-signature test.

Run from backend/:  python scripts/download_testdata.py
"""
import json
import os
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_testdata")
UA = {"User-Agent": "SangamHackathon/0.1 (testing; contact: hackathon@example.org)"}


def _get(url, dest, binary=True):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    mode = "wb" if binary else "w"
    with open(dest, mode) as f:
        f.write(data)
    return len(data)


def download_commons(query, count, prefix, sub="crowd"):
    d = os.path.join(OUT, sub)
    os.makedirs(d, exist_ok=True)
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           "&generator=search&gsrnamespace=6&gsrlimit=%d&gsrsearch=%s"
           "&prop=imageinfo&iiprop=url|mime&iiurlwidth=500"
           % (count, urllib.parse.quote(query)))
    try:
        req = urllib.request.Request(api, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            js = json.loads(r.read())
    except Exception as e:
        print(f"  COMMONS API FAIL ({query}): {e}")
        return
    pages = (js.get("query") or {}).get("pages", {})
    i = 0
    for _, p in pages.items():
        info = (p.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        url = info.get("thumburl") or info.get("url")
        if not url or "image/" not in mime:
            continue
        ext = ".jpg" if "jpeg" in mime else "." + mime.split("/")[-1]
        dest = os.path.join(d, f"{prefix}_{i}{ext}")
        try:
            n = _get(url, dest)
            print(f"  crowd {prefix}_{i}{ext:5} {n//1024} KB  <- {p.get('title','')[:50]}")
            i += 1
        except Exception as e:
            print(f"  CROWD FAIL {url}: {e}")


if __name__ == "__main__":
    import urllib.parse  # noqa
    # Face same/different validation: several photos of one person + others.
    print("[faces] Wikimedia (same-person pairs + different people)")
    download_commons("Narendra Modi official portrait", 4, "personA", sub="faces")
    download_commons("Barack Obama portrait", 2, "personB", sub="faces")
    download_commons("Sachin Tendulkar portrait", 2, "personC", sub="faces")
    # Cloth colour signal: distinctly coloured Indian attire.
    print("[crowd] Wikimedia (coloured Indian attire + Kumbh crowd)")
    download_commons("sadhu orange saffron robe", 3, "saffron")
    download_commons("woman red saree portrait", 3, "redsaree")
    download_commons("man white kurta india", 3, "white")
    download_commons("Kumbh Mela crowd pilgrims", 3, "kumbh")
    print(f"\nSaved under {OUT}")
