#!/usr/bin/env python3
"""Fetch public YouTube caption tracks when they are exposed on the watch page.

This does NOT require cookies, but only works if the video exposes captionTracks.
It avoids yt-dlp (which may trigger bot checks).

Usage:
  youtube_public_captions.py <video_id> [preferred_langs_csv]

Outputs caption text (no timestamps) to stdout.
Exit 0 even if no captions; prints empty string.
"""

import html
import json
import re
import sys
import urllib.parse
import urllib.request


def fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) OpenClawTranscriptBot/1.0"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def extract_caption_tracks(watch_html: str):
    # captionTracks appears inside ytInitialPlayerResponse JSON.
    # We'll regex the JSON blob conservatively.
    m = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.*?\})\s*;\s*", watch_html, flags=re.DOTALL)
    if not m:
        # Sometimes it's inside a script tag as JSON in quotes.
        m = re.search(r"\"captionTracks\"\s*:\s*\[(.*?)\]", watch_html, flags=re.DOTALL)
        if not m:
            return []
        # Not enough context to parse reliably
        return []

    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    try:
        tracks = (
            data.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks", [])
        )
        return tracks or []
    except Exception:
        return []


def download_track_text(track_url: str, timeout: int = 25) -> str:
    # Request as JSON3 (more compact/easier).
    parsed = urllib.parse.urlparse(track_url)
    q = dict(urllib.parse.parse_qsl(parsed.query))
    q["fmt"] = "json3"
    new_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(q)))

    raw = fetch(new_url, timeout=timeout)
    try:
        data = json.loads(raw)
    except Exception:
        # fallback: xml timedtext
        xml = raw
        # strip tags
        text = re.sub(r"<[^>]+>", " ", xml)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    events = data.get("events", [])
    parts = []
    for ev in events:
        for seg in ev.get("segs", []) or []:
            t = seg.get("utf8")
            if t:
                parts.append(t.replace("\n", " "))
    text = " ".join(parts)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    if len(sys.argv) < 2:
        print("", end="")
        return 0

    video_id = sys.argv[1].strip()
    langs = ["pt", "pt-BR", "en", "en-US"]
    if len(sys.argv) >= 3 and sys.argv[2].strip():
        langs = [x.strip() for x in sys.argv[2].split(",") if x.strip()]

    watch_html = fetch(f"https://www.youtube.com/watch?v={video_id}")
    tracks = extract_caption_tracks(watch_html)
    if not tracks:
        print("", end="")
        return 0

    # Choose best match by languageCode
    def score(tr):
        code = (tr.get("languageCode") or "").lower()
        try:
            idx = [l.lower() for l in langs].index(code)
            return idx
        except ValueError:
            return 999

    tracks_sorted = sorted(tracks, key=score)
    best = tracks_sorted[0]
    url = best.get("baseUrl")
    if not url:
        print("", end="")
        return 0

    text = download_track_text(url)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
