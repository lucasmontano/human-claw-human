#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import shutil

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

HANDLE_URL = "https://www.youtube.com/@lucasmontano"
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "lucasmontano_last_video.json")


def fetch(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) OpenClawTranscriptBot/1.0"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def extract_channel_id(html: str) -> str:
    # YouTube pages include: "channelId":"UC..."
    m = re.search(r'"channelId"\s*:\s*"(UC[0-9A-Za-z_-]{20,})"', html)
    if m:
        return m.group(1)
    # Alternate: "externalId":"UC..."
    m = re.search(r'"externalId"\s*:\s*"(UC[0-9A-Za-z_-]{20,})"', html)
    if m:
        return m.group(1)
    raise RuntimeError("Could not extract channelId from channel page")


def get_latest_video(channel_id: str) -> dict:
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    xml_bytes = fetch(feed_url)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    root = ET.fromstring(xml_bytes)
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise RuntimeError("No <entry> in feed")

    vid = entry.findtext("yt:videoId", default="", namespaces=ns).strip()
    title = entry.findtext("atom:title", default="", namespaces=ns).strip()
    published = entry.findtext("atom:published", default="", namespaces=ns).strip()
    link_el = entry.find("atom:link", ns)
    link = link_el.get("href") if link_el is not None else f"https://www.youtube.com/watch?v={vid}"

    return {"channel_id": channel_id, "feed_url": feed_url, "video_id": vid, "title": title, "published": published, "link": link}


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


def _vtt_to_text(vtt: str) -> str:
    # Remove WEBVTT headers and timestamps
    out_lines = []
    for line in vtt.splitlines():
        line = line.strip("\ufeff").strip()
        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}", line):
            continue
        if re.match(r"^\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}\.\d{3}", line):
            continue
        # Drop cue settings like "align:start position:0%"
        if re.search(r"align:|position:|line:", line):
            continue
        out_lines.append(line)
    text = " ".join(out_lines)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _transcript_via_ytdlp(video_url: str) -> str:
    """Best-effort subtitle fetch via yt-dlp (manual or auto captions)."""
    import subprocess
    import tempfile

    if not shutil.which("yt-dlp"):
        return ""

    with tempfile.TemporaryDirectory() as tmp:
        # Try Portuguese first, then English.
        for lang in ("pt", "pt-BR", "en"):
            # 1) manual subtitles
            cmd = [
                "yt-dlp",
                "--skip-download",
            ]
            cookies = os.environ.get("YT_COOKIES")
            if cookies and os.path.exists(cookies):
                cmd += ["--cookies", cookies]
            cmd += [
                "--write-subs",
                "--sub-langs",
                lang,
                "--sub-format",
                "vtt",
                "-o",
                os.path.join(tmp, "%(id)s.%(ext)s"),
                video_url,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            vtts = [p for p in os.listdir(tmp) if p.endswith(".vtt")]
            if vtts:
                vtt_path = os.path.join(tmp, vtts[0])
                with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
                    return _vtt_to_text(f.read())

            # 2) auto captions
            cmd = [
                "yt-dlp",
                "--skip-download",
            ]
            cookies = os.environ.get("YT_COOKIES")
            if cookies and os.path.exists(cookies):
                cmd += ["--cookies", cookies]
            cmd += [
                "--write-auto-sub",
                "--sub-langs",
                lang,
                "--sub-format",
                "vtt",
                "-o",
                os.path.join(tmp, "%(id)s.%(ext)s"),
                video_url,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            vtts = [p for p in os.listdir(tmp) if p.endswith(".vtt")]
            if vtts:
                vtt_path = os.path.join(tmp, vtts[0])
                with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
                    return _vtt_to_text(f.read())

    return ""


def get_transcript_text(video_id: str, video_url: str, max_chars: int = 6000) -> str:
    # 1) Try the transcript API (fast)
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["pt", "pt-BR", "en", "en-US"])
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        segments = []
    except Exception:
        segments = []

    text = " ".join((seg.get("text") or "").replace("\n", " ").strip() for seg in segments if seg.get("text"))
    text = re.sub(r"\s+", " ", text).strip()

    # 2) Fallback to yt-dlp subtitle extraction
    if not text:
        text = _transcript_via_ytdlp(video_url)

    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text


def main() -> int:
    html = fetch(HANDLE_URL).decode("utf-8", errors="ignore")
    channel_id = extract_channel_id(html)

    latest = get_latest_video(channel_id)
    state = load_state()
    last_vid = state.get("video_id")
    is_new = latest["video_id"] != last_vid

    now = int(time.time())
    state["last_seen_unix"] = now

    print(f"NEW_VIDEO={str(is_new).lower()}")
    print(f"CHANNEL_ID={channel_id}")
    print(f"VIDEO_ID={latest['video_id']}")
    print(f"VIDEO_URL={latest.get('link')}")
    print(f"TITLE={latest.get('title','')}")
    print("")

    transcript = get_transcript_text(latest["video_id"], latest.get("link") or f"https://www.youtube.com/watch?v={latest['video_id']}")

    if is_new:
        state.update({
            "video_id": latest["video_id"],
            "title": latest.get("title", ""),
            "url": latest.get("link", ""),
            "published": latest.get("published", ""),
            "processed_unix": now,
        })

    save_state(state)

    print("===TRANSCRIPT_SNIPPET_START===")
    if transcript:
        print(transcript)
    else:
        print("(No transcript available via API; use title/description only.)")
    print("===TRANSCRIPT_SNIPPET_END===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
