"""
TV/Radio Stream Monitor — captures live streams and transcribes with Gemini.

Pipeline:
  1. FFmpeg captures 60-second audio chunks from HLS/HTTP streams
  2. Gemini Audio API transcribes each chunk to text
  3. Keyword matching flags relevant mentions
  4. Matched transcripts stored in DB + alerts sent

Usage:
    python -m src.tv_radio_monitor            # run monitor
    python -m src.tv_radio_monitor --seed      # seed default stations
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, "/app")

from src.database import SessionLocal
from src.models import BroadcastStation, Transcript

logger = logging.getLogger(__name__)

# ── Configuration ──

CHUNK_DURATION_SECONDS = 60  # 1-minute audio chunks
MAX_CONCURRENT_STATIONS = 5  # Don't overload VPS
GEMINI_MODEL = "gemini-2.0-flash"
AUDIO_FORMAT = "wav"  # Gemini accepts wav
SAMPLE_RATE = 16000    # 16kHz mono = optimal for speech

# Keywords to match (case-insensitive) — configurable per client later
DEFAULT_KEYWORDS = [
    # Politics / Government
    "prezydent", "premier", "sejm", "senat", "rząd", "minister",
    "koalicja", "opozycja", "ustawa", "budżet",
    # Economy
    "inflacja", "stopy procentowe", "NBP", "giełda", "GPW",
    "bezrobocie", "PKB", "recesja", "podatki",
    # Events / Crisis
    "wypadek", "pożar", "powódź", "zamach", "protest",
    "strajk", "ewakuacja", "alarm",
    # Tech
    "sztuczna inteligencja", "cyberbezpieczeństwo",
]

# ── Default Polish stations ──

DEFAULT_STATIONS = [
    # TV
    {"name": "TVP Info", "type": "tv",
     "url": "https://cdn-main.lolokoko.tv/TVPInfo.stream/playlist.m3u8"},
    {"name": "TVP1", "type": "tv",
     "url": "https://cdn-main.lolokoko.tv/TVP1.stream/playlist.m3u8"},
    # Radio — Polskie Radio (official HTTP streams)
    {"name": "Polskie Radio 1 (Jedynka)", "type": "radio",
     "url": "http://mp3.polskieradio.pl:8900/;"},
    {"name": "Polskie Radio 3 (Trójka)", "type": "radio",
     "url": "http://mp3.polskieradio.pl:8904/;"},
    {"name": "Polskie Radio 4 (Czwórka)", "type": "radio",
     "url": "http://mp3.polskieradio.pl:8906/;"},
    # Radio — commercial
    {"name": "RMF FM", "type": "radio",
     "url": "https://rs6-krk2.rmfstream.pl/rmf_fm"},
    {"name": "Radio ZET", "type": "radio",
     "url": "https://zt.cdn.eurozet.pl/zet-net.mp3"},
    {"name": "TOK FM", "type": "radio",
     "url": "https://zt.cdn.eurozet.pl/tok-fm.mp3"},
    {"name": "Radio Maryja", "type": "radio",
     "url": "https://radiomaryja.fastcast4u.com/proxy/radiomaryja?mp=/1"},
    {"name": "RMF24", "type": "radio",
     "url": "https://rs6-krk2.rmfstream.pl/rmf_maxxx"},
]


def seed_stations():
    """Seed default broadcast stations into the database."""
    db = SessionLocal()
    try:
        existing = {s.name for s in db.query(BroadcastStation).all()}
        added = 0
        for st in DEFAULT_STATIONS:
            if st["name"] not in existing:
                db.add(BroadcastStation(
                    name=st["name"],
                    station_type=st["type"],
                    stream_url=st["url"],
                    language="pl",
                    is_active=True,
                ))
                added += 1
        db.commit()
        logger.info("Seeded %d broadcast stations (%d existing)", added, len(existing))
        return added
    finally:
        db.close()


def capture_audio_chunk(stream_url: str, duration: int = CHUNK_DURATION_SECONDS) -> str | None:
    """Capture audio from a stream URL using FFmpeg. Returns path to temp WAV file."""
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="/tmp")
        tmp.close()

        cmd = [
            "ffmpeg", "-y",
            "-i", stream_url,
            "-t", str(duration),
            "-vn",  # no video
            "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE),
            "-ac", "1",  # mono
            "-f", "wav",
            tmp.name,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=duration + 30
        )

        if result.returncode != 0:
            logger.warning("FFmpeg failed for %s: %s", stream_url[:50], result.stderr[-200:])
            os.unlink(tmp.name)
            return None

        # Verify file has content (>1KB = real audio)
        if os.path.getsize(tmp.name) < 1024:
            logger.warning("Audio file too small for %s", stream_url[:50])
            os.unlink(tmp.name)
            return None

        return tmp.name

    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg timeout for %s", stream_url[:50])
        return None
    except Exception as e:
        logger.exception("Audio capture error for %s: %s", stream_url[:50], e)
        return None


def transcribe_with_gemini(audio_path: str) -> str | None:
    """Transcribe audio file using Gemini Audio API."""
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not set")
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Upload audio file
        audio_file = genai.upload_file(audio_path, mime_type="audio/wav")

        # Transcribe
        response = model.generate_content(
            [
                "Transkrybuj poniższe nagranie audio na tekst. "
                "Zwróć TYLKO transkrypcję, bez komentarzy. "
                "Jeśli audio jest niezrozumiałe lub cisza, napisz '[cisza]'. "
                "Zachowaj oryginalny język.",
                audio_file,
            ],
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                max_output_tokens=4096,
            ),
        )

        text = response.text.strip() if response.text else None

        # Clean up uploaded file
        try:
            audio_file.delete()
        except Exception:
            pass

        return text

    except Exception as e:
        logger.exception("Gemini transcription failed: %s", e)
        return None


def match_keywords(text: str, keywords: list[str] | None = None) -> list[str]:
    """Match keywords in transcribed text (case-insensitive)."""
    if not text or text == "[cisza]":
        return []

    kws = keywords or DEFAULT_KEYWORDS
    text_lower = text.lower()
    matched = []
    for kw in kws:
        if kw.lower() in text_lower:
            matched.append(kw)
    return matched


def process_station(station: BroadcastStation) -> dict:
    """Capture + transcribe + match for a single station."""
    now = datetime.utcnow()
    result = {"station": station.name, "text": None, "keywords": [], "stored": False}

    logger.info("📡 Capturing %ds from %s...", CHUNK_DURATION_SECONDS, station.name)

    # 1. Capture audio
    audio_path = capture_audio_chunk(station.stream_url)
    if not audio_path:
        result["error"] = "capture_failed"
        return result

    try:
        # 2. Transcribe
        text = transcribe_with_gemini(audio_path)
        result["text"] = text

        if not text or text == "[cisza]":
            logger.info("  %s: silence/empty", station.name)
            return result

        # 3. Match keywords
        matched = match_keywords(text)
        result["keywords"] = matched

        # 4. Store in DB (always store, flag if keywords found)
        db = SessionLocal()
        try:
            transcript = Transcript(
                station_id=station.id,
                text=text,
                chunk_start=now,
                chunk_end=now + timedelta(seconds=CHUNK_DURATION_SECONDS),
                keywords_found=", ".join(matched) if matched else None,
            )
            db.add(transcript)
            db.commit()
            result["stored"] = True

            if matched:
                logger.info("  🔑 %s: MATCH [%s] in: %s...",
                           station.name, ", ".join(matched), text[:100])
                # Send Discord alert for keyword matches
                try:
                    from src.discord_notifier import send_discord
                    send_discord(
                        title=f"📡 {station.name} — keyword match",
                        description=(
                            f"**Keywords**: {', '.join(matched)}\n"
                            f"**Fragment**: {text[:300]}..."
                        ),
                        level="warning",
                    )
                except Exception:
                    pass
            else:
                logger.info("  ✅ %s: transcribed %d chars (no keywords)", station.name, len(text))

        finally:
            db.close()

    finally:
        # Clean up temp audio
        try:
            os.unlink(audio_path)
        except Exception:
            pass

    return result


def run_monitoring_cycle():
    """Run one monitoring cycle for all active stations."""
    db = SessionLocal()
    try:
        stations = db.query(BroadcastStation).filter(BroadcastStation.is_active).all()
        if not stations:
            logger.info("No active broadcast stations configured")
            return []

        logger.info("🎙️ Broadcast monitor: %d active stations", len(stations))
        results = []

        for station in stations[:MAX_CONCURRENT_STATIONS]:
            try:
                result = process_station(station)
                results.append(result)
            except Exception as e:
                logger.exception("Station %s failed: %s", station.name, e)
                results.append({"station": station.name, "error": str(e)})

        keywords_total = sum(len(r.get("keywords", [])) for r in results)
        transcribed = sum(1 for r in results if r.get("stored"))
        logger.info("📊 Cycle: %d/%d transcribed, %d keyword matches",
                    transcribed, len(results), keywords_total)

        return results

    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if "--seed" in sys.argv:
        print("🌱 Seeding broadcast stations...")
        added = seed_stations()
        print(f"  Added {added} stations")
    else:
        print("\n📡 TV/Radio Monitor — single cycle")
        print("=" * 50)
        results = run_monitoring_cycle()
        for r in results:
            status = "✅" if r.get("stored") else "❌"
            kws = f" [🔑 {', '.join(r['keywords'])}]" if r.get("keywords") else ""
            print(f"  {status} {r['station']}{kws}")
