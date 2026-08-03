#!/usr/bin/env python3
"""Audit index.html against the live App Store.

Read-only. Reports drift; never edits. Run before hand-editing tiles, and from
the nightly command-center refresh so an approval becomes a notification instead
of something noticed weeks later.

    python3 check.py           # human-readable
    python3 check.py --quiet   # print only when there IS drift (for cron)

Exit 0 = no drift, 1 = drift found, 2 = couldn't check.
"""

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
INDEX = HERE / "index.html"
ASC = Path.home() / ".claude/skills/command-center/asc.rb"
LOOKUP = "https://itunes.apple.com/lookup?id={}&country=us"

QUIET = "--quiet" in sys.argv


def tiles():
    """Every tile in index.html: (appid, display name, is_in_review)."""
    html = INDEX.read_text()
    out = []
    for m in re.finditer(
        r'<(?P<tag>a|div) class="tile" data-appid="(?P<id>\d+)"(?P<rest>.*?)</(?P=tag)>',
        html,
        re.S,
    ):
        name = re.search(r'class="t-name">(.*?)</p>', m.group("rest"), re.S)
        out.append(
            (
                m.group("id"),
                re.sub(r"\s+", " ", name.group(1)).strip() if name else "?",
                m.group("tag") == "div",
            )
        )
    return out


def store(appid):
    """Public App Store record, or None if not published yet."""
    try:
        with urllib.request.urlopen(LOOKUP.format(appid), timeout=15) as r:
            data = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"_error": str(e)}
    return data["results"][0] if data.get("resultCount") else None


def fleet():
    """Everything in App Store Connect, via the command-center puller."""
    if not ASC.exists():
        return None
    try:
        out = subprocess.run(
            ["/usr/bin/ruby", str(ASC)], capture_output=True, text=True, timeout=90
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    apps = {}
    for m in re.finditer(r"(\d{9,})", out):
        apps[m.group(1)] = True
    return apps


def main():
    if not INDEX.exists():
        print("check: index.html not found", file=sys.stderr)
        return 2

    listed = tiles()
    if not listed:
        print("check: no tiles parsed out of index.html — did the markup change?")
        return 2

    drift = []

    for appid, name, in_review in listed:
        rec = store(appid)
        if rec and "_error" in rec:
            print(f"  ? {name}: lookup failed ({rec['_error']})")
            continue
        if rec is None:
            if not in_review:
                drift.append(
                    f"LIVE TILE IS DEAD  {name} (id {appid}) — the App Store has no "
                    f"such app. The link 404s."
                )
            continue
        # Published. Is it still on the review shelf?
        if in_review:
            drift.append(
                f"APPROVED  {name} (id {appid}) is live as "
                f"\"{rec['trackName']}\" — promote it out of the review shelf "
                f"and make the tile a link."
            )
        else:
            if rec["trackName"] not in name and name not in rec["trackName"]:
                drift.append(
                    f"RENAMED   tile says \"{name}\", store says "
                    f"\"{rec['trackName']}\" (id {appid})"
                )
            html = INDEX.read_text()
            price = rec.get("formattedPrice", "")
            block = re.search(
                rf'data-appid="{appid}".*?</a>', html, re.S
            )
            shown_paid = block and "paid" in block.group(0)
            is_paid = price not in ("Free", "", None)
            if is_paid and not shown_paid:
                drift.append(f"PRICE     {name} is {price} but the tile shows no price")
            elif not is_paid and shown_paid:
                drift.append(f"PRICE     {name} is now Free but the tile shows a price")
            elif is_paid and shown_paid and price not in block.group(0):
                drift.append(f"PRICE     {name} is {price}; the tile says otherwise")

    # Anything live in ASC that never made it onto the page?
    known = {a for a, _, _ in listed}
    asc = fleet()
    if asc:
        for appid in asc:
            if appid in known:
                continue
            rec = store(appid)
            if rec and "_error" not in rec:
                drift.append(
                    f"MISSING   \"{rec['trackName']}\" (id {appid}) is on the App "
                    f"Store but has no tile"
                )

    # Header claim: "Seven on the App Store. Three in review."
    words = "zero one two three four five six seven eight nine ten eleven twelve".split()
    live = sum(1 for _, _, r in listed if not r)
    soon = sum(1 for _, _, r in listed if r)
    head = INDEX.read_text()
    claim = re.search(r'class="count">(.*?)</p>', head, re.S)
    if claim:
        txt = claim.group(1).lower()
        if live < len(words) and words[live] not in txt:
            drift.append(
                f"HEADER    page has {live} live tiles but the header reads "
                f"\"{re.sub(r'\\s+', ' ', claim.group(1)).strip()}\""
            )
        elif soon < len(words) and words[soon] not in txt:
            drift.append(
                f"HEADER    page has {soon} in-review tiles but the header reads "
                f"\"{re.sub(r'\\s+', ' ', claim.group(1)).strip()}\""
            )

    if drift:
        print(f"riverroadlabs.app — {len(drift)} thing(s) to fix:\n")
        for d in drift:
            print(f"  • {d}")
        print(f"\n  edit {INDEX}")
        return 1

    if not QUIET:
        print(f"riverroadlabs.app — no drift ({live} live, {soon} in review)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
