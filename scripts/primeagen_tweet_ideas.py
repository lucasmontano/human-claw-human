#!/usr/bin/env python3
import json
import os
import re
import sys
import textwrap
import time
import urllib.request
import xml.etree.ElementTree as ET

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

CHANNEL_ID = "UC8butISFwT-Wl7EV0hUK0BQ"  # ThePrimeagen
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "primeagen_last_video.json")


def fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) OpenClawPrimeagenBot/1.0"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_latest_video_from_feed(xml_bytes: bytes) -> dict:
    # Atom feed with namespaces
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    root = ET.fromstring(xml_bytes)
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise RuntimeError("No <entry> found in feed")

    vid = entry.findtext("yt:videoId", default="", namespaces=ns).strip()
    title = entry.findtext("atom:title", default="", namespaces=ns).strip()
    published = entry.findtext("atom:published", default="", namespaces=ns).strip()
    link_el = entry.find("atom:link", ns)
    link = link_el.get("href") if link_el is not None else ""

    if not vid:
        raise RuntimeError("No videoId found in latest entry")

    return {"video_id": vid, "title": title, "published": published, "link": link}


def load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_transcript(video_id: str) -> str:
    # Prefer English, but allow fallback.
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        # Fallback: try any available transcript
        try:
            tl = YouTubeTranscriptApi.list_transcripts(video_id)
            t = None
            # Try manually created first
            for tr in tl:
                if tr.is_generated is False:
                    t = tr
                    break
            if t is None:
                t = tl.find_generated_transcript(tl._TranscriptList__transcripts.keys())  # best-effort
            segments = t.fetch() if t is not None else []
        except Exception:
            segments = []

    joined = " ".join(clean_text(seg.get("text", "")) for seg in segments if seg.get("text"))
    return joined


def chunk_text(s: str, max_chars: int = 6000) -> str:
    # Keep it short for LLM prompt + WhatsApp.
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "…"


def main() -> int:
    xml_bytes = fetch(FEED_URL)
    latest = get_latest_video_from_feed(xml_bytes)

    state = load_state()
    last_vid = state.get("video_id")

    is_new = latest["video_id"] != last_vid

    # Always update "last_seen"; only update video_id when actually processing.
    now = int(time.time())
    state["last_seen_unix"] = now

    # Print machine-readable header line for the agent.
    print(f"NEW_VIDEO={str(is_new).lower()}")
    print(f"VIDEO_ID={latest['video_id']}")
    print(f"VIDEO_URL={latest.get('link') or 'https://www.youtube.com/watch?v=' + latest['video_id']}")
    print(f"TITLE={latest.get('title','')}")
    print("")

    if not is_new:
        print("No new ThePrimeagen video since last check.")
        save_state(state)
        return 0

    transcript = get_transcript(latest["video_id"])
    transcript = chunk_text(transcript)

    state.update({
        "video_id": latest["video_id"],
        "title": latest.get("title", ""),
        "url": latest.get("link") or f"https://www.youtube.com/watch?v={latest['video_id']}",
        "published": latest.get("published", ""),
        "processed_unix": now,
    })
    save_state(state)

    # Output a prompt block the agent will use to generate tweet ideas.
    print("===TRANSCRIPT_SNIPPET_START===")
    if transcript:
        print(transcript)
    else:
        print("(No transcript available via API; generate ideas based on title only.)")
    print("===TRANSCRIPT_SNIPPET_END===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
