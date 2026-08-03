# riverroadlabs.app

Umbrella landing page for the artisanally crafted River Road Labs iOS apps.

Copy is studio-voiced ("the team at River Road Labs") — keep personal names out of
the page text. Apple still lists the seller name on every App Store listing, so
this is a tone choice, not privacy. Static, self-contained,
served by GitHub Pages at <https://riverroadlabs.app>.

## Rules

- **Keep it under ~2 MB.** No video, no app screenshots, no reels. This is a
  link-in-bio page, not a CDN — `timestable400-site` already plays that role and
  is 380 MB because of it.
- **No build step.** `index.html` is hand-written with an inline `<style>`. Tiles
  carry `data-appid` so `check.py` can audit them against the live App Store.
- **No JavaScript.** Link scrapers (Instagram, TikTok, iMessage) don't run JS; a
  JS-rendered page would preview as an empty card.
- **Relative asset paths only** (`icons/foo.webp`, never `/icons/foo.webp`) so the
  page still works at the `qxxx5vyd77-byte.github.io/riverroadlabs-site/` fallback.

## Layout

    index.html          the page
    privacy.html        studio-level policy; links out to each app's own policy
    check.py            drift auditor — run it before editing tiles by hand
    icons/              10 app icons, 256px webp, ~112 KB total
    og.jpg              1200x630 link-preview card
    appstore-badge.svg  Apple's official badge artwork, unmodified

## Adding an app

1. Export the icon: `magick <AppIcon>.png -resize 256x256 -strip -quality 82 icons/<slug>.webp`
2. Copy a tile in `index.html`, set `data-appid`, name, one-line promise, category.
3. Add its privacy policy link to `privacy.html`.
4. Run `python3 check.py` — it should report no drift.

The one-line promise is editorial. It comes from the app's real App Store copy,
scoped to what the app actually does. Don't let it drift into a claim.
