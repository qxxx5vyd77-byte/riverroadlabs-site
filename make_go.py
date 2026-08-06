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
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
INDEX = HERE / "index.html"
OUT = HERE / "go"
CHECK = "--check" in sys.argv

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
    <p>If nothing happens, tap below.</p>
    <a class="btn" href="{web}">Open in the App Store</a>
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
  var t = setTimeout(function () {{ window.location.replace(web); }}, 1400);
  document.addEventListener("visibilitychange", function () {{
    if (document.hidden) clearTimeout(t);
  }});
  window.addEventListener("pagehide", function () {{ clearTimeout(t); }});
  window.location.href = scheme;
}})();
</script>
<noscript><meta http-equiv="refresh" content="0;url={web}"></noscript>
</body>
</html>
"""


def main():
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
