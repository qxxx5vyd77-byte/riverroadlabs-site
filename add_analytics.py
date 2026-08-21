#!/usr/bin/env python3
"""Install (or remove) the Cloudflare Web Analytics beacon across riverroadlabs.app.

WHY CLOUDFLARE AND NOT GA (2026-08-19, Matt's call):
  * Free, commercial use permitted.
  * Sets NO cookies -> needs NO consent banner. That is the deciding factor: 10 of the
    13 pages are /go/ App Store hand-offs, and a consent banner on a conversion page
    would cost more traffic than the analytics could ever explain.
  * One tag, no build step, works on GitHub Pages without proxying the domain.

⚠️ THE THING THAT MAKES THIS NON-TRIVIAL — THE /go/ PAGES REDIRECT.
Each /go/<appid>/ page runs `window.location.href = 'itms-apps://...'` immediately, with an
https fallback at 1400ms. A first instinct is that the page unloads instantly and no beacon
could ever fire. That is WRONG, and the page's own comment says why: itms-apps:// is a SCHEME
HAND-OFF, not a navigation — the page is BACKGROUNDED, not destroyed, and `visibilitychange`
fires. So the document survives ~1.2-1.4s at minimum, which is ample for the beacon.

Therefore: same tag everywhere, injected EARLY in <head> so the fetch starts before the
redirect script runs. Do NOT add `defer` on the /go/ pages — defer waits for parsing to
finish, which on those pages is the same tick the redirect fires in.

⛔ INTERPRETATION RULE (advisor, 2026-08-21): a ZERO in CF /go/ data is AMBIGUOUS between
"nobody clicked" and "the beacon never fires" until ONE /go/ hit is confirmed end-to-end.
Until then no /go/ number is evidence about content performance. Homepage views do NOT
validate /go/ — the homepage never navigates away, so it exercises none of the risky path.

THE THREE PATHS SPLIT CLEANLY (test separately):
  1. in-app webview (IG/TikTok/FB): iOS blocks the itms scheme, no navigation ever happens,
     page stays open -> beacon should always land. This is most real traffic.
  2. normal mobile browser, scheme resolves: page BACKGROUNDS (not destroyed); open question
     is whether CF has sent by then.
  3. desktop / scheme fails: the 1400ms fallback is location.replace() -> document DESTROYED.
     Cold-cache third-party fetch+execute can lose that race. The "+250ms delay" fix below
     helps ONLY this case.

THE CONTROL: Matt deliberately taps one /go/ link at a NOTED TIME from a NOTED APP (IG
in-app browser = the valuable case), then look for that exact path in CF. Establish the
dashboard's ingest lag on a known-good homepage hit first — do not call a miss against an
unknown lag. FREE TRIANGULATION: ASC "Web referrer" page views (funnel.rb / ground-truth,
~2-day lag) measure the same event independently; CF stuck at 0 while ASC web-referrer
moves = beacon broken, no device test needed.

⛔ VERIFY EMPIRICALLY AFTER INSTALL. The reasoning above is sound but untested. Load a /go/
page on a real phone from a real social app and confirm the hit appears in Cloudflare. If
/go/ hits do NOT register, the fix is to delay the scheme hand-off by ~250ms — but do not
pre-emptively add that delay, because it degrades the conversion path this site exists for.

Usage:
    python3 add_analytics.py --token <CF_TOKEN>     # install
    python3 add_analytics.py --remove               # clean removal
    python3 add_analytics.py --check                # report current state
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
MARK_OPEN = "<!-- rrl-analytics -->"
MARK_CLOSE = "<!-- /rrl-analytics -->"

# Not deferred, and placed early in <head>: on the /go/ pages the redirect fires in the same
# tick that parsing completes, so a deferred script would lose the race.
SNIPPET = (
    '{o}\n'
    '<script src="https://static.cloudflareinsights.com/beacon.min.js" '
    "data-cf-beacon='{{\"token\": \"{token}\"}}'></script>\n"
    '{c}'
)


def pages():
    return sorted(ROOT.rglob("index.html"))


def strip(html):
    """Remove a previous install. Idempotent — safe to run on a clean file."""
    return re.sub(
        re.escape(MARK_OPEN) + r".*?" + re.escape(MARK_CLOSE) + r"\n?",
        "",
        html,
        flags=re.S,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    files = pages()
    if not files:
        sys.exit("no index.html found — wrong directory?")

    if a.check:
        for f in files:
            h = f.read_text()
            state = "INSTALLED" if MARK_OPEN in h else "—"
            print(f"  {state:10} {f.relative_to(ROOT)}")
        return

    if a.remove:
        n = 0
        for f in files:
            h = f.read_text()
            if MARK_OPEN in h:
                f.write_text(strip(h))
                n += 1
        print(f"removed from {n} page(s)")
        return

    if not a.token:
        sys.exit("need --token (from Cloudflare > Web Analytics > your site)")

    snippet = SNIPPET.format(o=MARK_OPEN, c=MARK_CLOSE, token=a.token)
    n = 0
    for f in files:
        h = strip(f.read_text())          # idempotent: never double-install
        if "<head>" not in h:
            print(f"  ⚠️  SKIPPED (no <head>): {f.relative_to(ROOT)}")
            continue
        # Immediately after <meta charset> when present, else right after <head>.
        m = re.search(r"<meta charset=[^>]*>", h, flags=re.I)
        anchor_end = m.end() if m else h.index("<head>") + len("<head>")
        h = h[:anchor_end] + "\n" + snippet + h[anchor_end:]
        f.write_text(h)
        n += 1
    print(f"installed on {n} page(s)")


if __name__ == "__main__":
    main()
