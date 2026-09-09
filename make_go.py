#!/usr/bin/env python3
"""Generate /go/<appid>/ App Store hand-off pages.

WHY THIS EXISTS
---------------
Instagram, TikTok and Facebook open bio links inside an in-app webview. A plain
https://apps.apple.com/... URL renders *as a web page* in that webview, where the
"Get" button is dead — the user has to find the "open in browser" menu themselves,
and almost nobody does. Two independent reports (2026-08-05) also say Meta is now
rejecting bare App Store URLs in the bio field outright.

The fix is a hand-off page: try the `itms-apps://` scheme first, which the OS routes
straight to the App Store app and which escapes the webview. Fall back to the normal
https URL if the scheme doesn't resolve (desktop, Android, anything odd).

This is ADDITIVE. It does not touch index.html or its tiles, so nothing that works
today can break. Point the tiles at /go/<id>/ only after the pages are verified live.

    python3 make_go.py          # write the pages
    python3 make_go.py --check  # list what WOULD be written, write nothing

⛔ THE TEMPLATE BELOW IS STALE (verified 2026-08-30). It predates the Cloudflare beacon and
the 2026-08-22 "hold the hand-off until the beacon has loaded" fix that the live pages carry.
Running the default mode REWRITES every live /go/<id>/index.html back to the old behaviour
and silently kills the analytics lane. Until the template is brought up to date, the live
pages are the ground truth, not this file. New bare pages: copy a known-good live page.

PER-SURFACE PATHS (2026-09-08, Matt: "Approve, build and push")
-----------------------------------------------------------------
    python3 make_go.py --surfaces          # write /go/<slug>/{ig,fb,tt,x}/index.html
    python3 make_go.py --surfaces --check  # report what differs, write nothing

Every bare /go/<slug>/index.html gets four BYTE-IDENTICAL copies at /go/<slug>/ig/,
/fb/, /tt/ and /x/. Same target, same beacon, same fallback — the only difference is the
path Cloudflare Web Analytics records, so a click can be attributed to the surface the
link was posted on (the kanji-fb / kanji-wk A/B pages proved the mechanism on 2026-09-01).
The bare path keeps working and stays the source: this mode reads the live bare page and
never touches it, so it is safe to re-run after any bare-page edit (idempotent — a copy is
rewritten only when its bytes differ). Pages use absolute URLs only, so the deeper path
changes nothing about what they load.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
INDEX = HERE / "index.html"
OUT = HERE / "go"
CHECK = "--check" in sys.argv
SURFACES_MODE = "--surfaces" in sys.argv

# One suffix per surface a link gets posted on. Add here to mint a new path fleet-wide.
SURFACES = ("ig", "fb", "tt", "x")

TILE = re.compile(
    r'<a class="tile" data-appid="(?P<id>\d+)"[^>]*>(?P<body>.*?)</a>', re.S
)
NAME = re.compile(r'<p class="t-name">(.*?)</p>', re.S)

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opening {name} in the App Store…</title>
<link rel="canonical" href="{web}">
<meta name="robots" content="noindex">
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    margin: 0; min-height: 100vh; display: flex; align-items: center;
    justify-content: center; padding: 24px;
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #faf9f6; color: #1a1a1a; text-align: center;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #101211; color: #e9ebe7; }}
    a.btn {{ background: #e9ebe7 !important; color: #101211 !important; }}
  }}
  .w {{ display: flex; flex-direction: column; gap: 14px; align-items: center; max-width: 30ch; }}
  h1 {{ font-size: 19px; margin: 0; font-weight: 650; }}
  p {{ margin: 0; opacity: .72; font-size: 14.5px; }}
  a.btn {{
    display: inline-block; margin-top: 6px; padding: 12px 22px; border-radius: 999px;
    background: #1a1a1a; color: #faf9f6; text-decoration: none; font-weight: 640;
  }}
  a.home {{ color: inherit; opacity: .55; font-size: 13px; }}
</style>
</head>
<body>
  <div class="w">
    <h1>Opening {name} in the App Store…</h1>
    <p id="sub">If nothing happens, tap below.</p>
    <a class="btn" href="{web}">Open in the App Store</a>
    <p id="iab" hidden style="font-size:13.5px;line-height:1.5;margin:16px 0 0;opacity:.85">
      <b>Still here?</b> <span id="iabtxt"></span>
    </p>
    <a class="home" href="https://riverroadlabs.app">River Road Labs</a>
  </div>
<script>
(function () {{
  var web = {web!r};
  var scheme = {scheme!r};
  // The scheme hand-off is the whole point: it leaves the in-app webview and opens
  // the App Store app. If it resolves, this page gets backgrounded and
  // visibilitychange fires — cancel the fallback so returning here doesn't bounce
  // the user a second time.
  // In-app browsers (Instagram/TikTok/Facebook) drop BOTH the itms-apps:// scheme and
  // the https fallback, so the old behaviour was: try scheme, fail, redirect to a page
  // whose Get button is also dead. The fallback WAS the dead end it existed to avoid.
  // Detect those webviews, skip the pointless https bounce, and say the one thing that
  // actually works — open it in the real browser. Verified on device 2026-08-06.
  var ua = navigator.userAgent || "";
  var app = /Instagram/i.test(ua) ? "Instagram"
          : /TikTok|musical_ly|Bytedance/i.test(ua) ? "TikTok"
          : /FBAN|FBAV|FB_IAB/i.test(ua) ? "Facebook" : null;

  var t = null;
  if (!app) {{
    t = setTimeout(function () {{ window.location.replace(web); }}, 1400);
  }} else {{
    var menu = app === "TikTok" ? "the \u22ef menu" : "the \u22ef menu at the top right";
    var choose = app === "TikTok" ? "\u201cOpen in browser\u201d" : "\u201cOpen in external browser\u201d";
    setTimeout(function () {{
      if (document.hidden) return;
      var el = document.getElementById("iab");
      document.getElementById("iabtxt").textContent =
        app + "'s browser can't open the App Store. Tap " + menu + ", choose " + choose +
        ", and this page will hand off properly.";
      el.hidden = false;
      document.getElementById("sub").textContent = "";
    }}, 1200);
  }}
  document.addEventListener("visibilitychange", function () {{
    if (document.hidden && t) clearTimeout(t);
  }});
  window.addEventListener("pagehide", function () {{ if (t) clearTimeout(t); }});
  window.location.href = scheme;
}})();
</script>
<noscript><meta http-equiv="refresh" content="0;url={web}"></noscript>
</body>
</html>
"""


def surfaces():
    """Mirror every bare /go/<slug>/index.html into /go/<slug>/<surface>/index.html, byte for byte."""
    bare = sorted(p for p in OUT.glob("*/index.html"))
    if not bare:
        print(f"no bare pages under {OUT} — run the default mode first")
        return 2
    written = same = 0
    for src in bare:
        slug = src.parent.name
        data = src.read_bytes()
        for sfx in SURFACES:
            dest = OUT / slug / sfx / "index.html"
            if dest.exists() and dest.read_bytes() == data:
                same += 1
                continue
            print(f"  {'would write' if CHECK else 'write'}  /go/{slug}/{sfx}/  (from /go/{slug}/)")
            if CHECK:
                written += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            written += 1
    verb = "would write" if CHECK else "wrote"
    print(f"\n{len(bare)} bare page(s) x {len(SURFACES)} surfaces: {verb} {written}, already identical {same}")
    return 0


def main():
    if SURFACES_MODE:
        return surfaces()
    html = INDEX.read_text()
    apps = []
    for m in TILE.finditer(html):
        aid = m.group("id")
        nm = NAME.search(m.group("body"))
        name = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", nm.group(1))).strip() if nm else f"app {aid}"
        apps.append((aid, name))

    if not apps:
        print("no tiles parsed — did index.html markup change?")
        return 2

    for aid, name in apps:
        web = f"https://apps.apple.com/us/app/id{aid}"
        scheme = f"itms-apps://apps.apple.com/us/app/id{aid}"
        dest = OUT / aid / "index.html"
        print(f"  /go/{aid}/  ->  {name}")
        if CHECK:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(PAGE.format(name=name, web=web, scheme=scheme))

    print(f"\n{'would write' if CHECK else 'wrote'} {len(apps)} hand-off pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
