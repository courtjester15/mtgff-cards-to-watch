from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .config import Settings
from .detection import locate_cards_to_watch
from .models import EpisodeCandidate

USER_AGENT = "FFW/0.2 (+https://github.com/courtjester15/mtgff-cards-to-watch)"
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/wav",
    "audio/x-wav", "audio/webm", "application/octet-stream",
}


def parse_episode_number(title: str, description: str = "") -> int:
    for text in (title, description):
        match = re.search(r"\b(?:ep(?:isode)?\.?\s*#?)(\d{1,5})\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _duration(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.strip().split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 3:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    return numbers[0] if numbers else None


def parse_rss(xml_bytes: bytes) -> list[EpisodeCandidate]:
    root = ET.fromstring(xml_bytes)
    episodes: list[EpisodeCandidate] = []
    for item in root.findall("./channel/item"):
        def value(name: str) -> str:
            node = item.find(name)
            return (node.text or "").strip() if node is not None else ""

        title = value("title") or "Untitled episode"
        description = value("description")
        enclosure = item.find("enclosure")
        audio_url = (enclosure.get("url") or "").strip() if enclosure is not None else ""
        parsed_audio = urlparse(audio_url)
        if parsed_audio.scheme != "https" or not parsed_audio.netloc:
            continue
        guid = value("guid")
        if not guid:
            guid = "enclosure-sha256:" + hashlib.sha256(audio_url.encode("utf-8")).hexdigest()
        published_raw = value("pubDate")
        try:
            published = parsedate_to_datetime(published_raw)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published_at = published.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError):
            continue
        creator = value("{http://purl.org/dc/elements/1.1/}creator") or value("{http://www.itunes.com/dtds/podcast-1.0.dtd}author")
        hosts = [part.strip() for part in re.split(r"\s*(?:,|&| and )\s*", creator) if part.strip()]
        duration = _duration(value("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration"))
        episodes.append(EpisodeCandidate(
            guid=guid,
            episode_number=parse_episode_number(title, description),
            title=title,
            published_at=published_at,
            audio_url=audio_url,
            episode_url=value("link") or audio_url,
            hosts=hosts,
            description=description or None,
            duration_seconds=duration,
            feed_metadata={
                "original_guid": value("guid") or None,
                "published_raw": published_raw,
                "enclosure_type": enclosure.get("type") if enclosure is not None else None,
                "enclosure_length": enclosure.get("length") if enclosure is not None else None,
            },
        ))
    unique = {episode.guid: episode for episode in episodes}
    return sorted(unique.values(), key=lambda episode: (episode.published_at, episode.guid))


class LiveFeedSource:
    def __init__(self, feed_url: str, timeout: int = 30, max_bytes: int = 2_000_000, opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self.feed_url = feed_url
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.opener = opener

    def episodes(self) -> list[EpisodeCandidate]:
        if urlparse(self.feed_url).scheme != "https":
            raise ValueError("FFW feed URL must use HTTPS.")
        request = urllib.request.Request(self.feed_url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"})
        with self.opener(request, timeout=self.timeout) as response:
            payload = response.read(self.max_bytes + 1)
            if len(payload) > self.max_bytes:
                raise ValueError("Podcast RSS exceeds the configured safety limit.")
            return parse_rss(payload)


class StreamingDownloader:
    def __init__(self, max_bytes: int, timeout: int, opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.opener = opener

    def download(self, episode: EpisodeCandidate, destination: Path) -> Path:
        if urlparse(episode.audio_url).scheme != "https":
            raise ValueError("Audio enclosure must use HTTPS.")
        destination = destination.with_suffix(".mp3")
        part = destination.with_suffix(destination.suffix + ".part")
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(episode.audio_url, headers={"User-Agent": USER_AGENT, "Accept": "audio/*"})
        try:
            with self.opener(request, timeout=self.timeout) as response, part.open("wb") as output:
                final_url = response.geturl()
                if urlparse(final_url).scheme != "https":
                    raise ValueError("Audio redirect did not remain on HTTPS.")
                content_type = response.headers.get_content_type().lower()
                if content_type not in ALLOWED_AUDIO_TYPES and not content_type.startswith("audio/"):
                    raise ValueError(f"Unexpected audio content type: {content_type}")
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > self.max_bytes:
                    raise ValueError("Audio exceeds configured maximum size.")
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise ValueError("Audio exceeds configured maximum size.")
                    output.write(chunk)
                if total == 0:
                    raise ValueError("Downloaded audio was empty.")
            part.replace(destination)
            return destination
        except Exception:
            part.unlink(missing_ok=True)
            raise


class FfmpegAudioProcessor:
    def __init__(self, chunk_seconds: int = 1200) -> None:
        self.chunk_seconds = chunk_seconds

    def prepare(self, source: Path, destination: Path) -> list[Path]:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required for live audio preparation.")
        output_dir = destination.parent / "chunks"
        output_dir.mkdir(parents=True, exist_ok=True)
        pattern = output_dir / "chunk-%03d.mp3"
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-f", "segment",
            "-segment_time", str(self.chunk_seconds), "-reset_timestamps", "1", str(pattern),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if completed.returncode:
            raise RuntimeError(f"ffmpeg failed: {completed.stderr[-500:]}")
        chunks = sorted(output_dir.glob("chunk-*.mp3"))
        if not chunks:
            raise RuntimeError("ffmpeg produced no audio chunks.")
        return chunks


class OpenAITranscriber:
    def __init__(self, model_name: str, chunk_seconds: int) -> None:
        self.model_name = model_name
        self.chunk_seconds = chunk_seconds

    def transcribe(self, episode: EpisodeCandidate, audio_files: list[Path]) -> dict[str, Any]:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for live transcription.")
        from openai import OpenAI
        client = OpenAI()
        segments: list[dict[str, Any]] = []
        texts: list[str] = []
        usage: list[dict[str, Any]] = []
        for index, path in enumerate(audio_files):
            with path.open("rb") as audio:
                response = client.audio.transcriptions.create(
                    model=self.model_name,
                    file=audio,
                    response_format="diarized_json",
                    chunking_strategy="auto",
                )
            payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)
            if payload.get("usage"):
                usage.append(payload["usage"])
            offset = index * self.chunk_seconds
            texts.append(str(payload.get("text", "")))
            for segment in payload.get("segments", []):
                segment = dict(segment)
                segment["start"] = float(segment.get("start", 0)) + offset
                segment["end"] = float(segment.get("end", segment["start"] - offset)) + offset
                segments.append(segment)
        segments.sort(key=lambda item: item["start"])
        return {
            "synthetic": False,
            "provider": "OpenAI",
            "model": self.model_name,
            "text": "\n".join(texts),
            "segments": segments,
            "chunk_count": len(audio_files),
            "duration_seconds": episode.duration_seconds,
            "usage": usage or None,
        }


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["recommendations", "review_reason"],
    "properties": {
        "review_reason": {"type": ["string", "null"]},
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["card", "printing", "printing_certainty", "foil", "hosts", "recommendation", "mentioned_price", "entry_target", "hold", "exit_target", "reasoning", "caveats", "confidence", "start_seconds", "end_seconds", "evidence_excerpt", "review_status", "review_reason"],
                "properties": {
                    "card": {"type": "string"}, "printing": {"type": ["string", "null"]},
                    "printing_certainty": {"type": ["string", "null"], "enum": ["confirmed", "likely", "ambiguous", None]},
                    "foil": {"type": ["boolean", "null"]}, "hosts": {"type": "array", "items": {"type": "string"}},
                    "recommendation": {"type": "string"}, "mentioned_price": {"type": ["string", "null"]},
                    "entry_target": {"$ref": "#/$defs/target"}, "hold": {"type": ["string", "null"]},
                    "exit_target": {"$ref": "#/$defs/target"}, "reasoning": {"type": "array", "items": {"type": "string"}},
                    "caveats": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": ["string", "null"], "enum": ["low", "medium", "high", None]},
                    "start_seconds": {"type": "integer"}, "end_seconds": {"type": ["integer", "null"]},
                    "evidence_excerpt": {"type": "string"},
                    "review_status": {"type": "string", "enum": ["approved", "pending", "needs_review"]},
                    "review_reason": {"type": ["string", "null"]},
                },
            },
        },
    },
    "$defs": {"target": {"type": ["object", "null"], "additionalProperties": False, "required": ["raw", "currency", "minimum", "maximum"], "properties": {"raw": {"type": "string"}, "currency": {"type": ["string", "null"]}, "minimum": {"type": ["number", "null"]}, "maximum": {"type": ["number", "null"]}}}},
}


class OpenAIExtractor:
    def __init__(self, model_name: str, card_glossary: str = "") -> None:
        self.model_name = model_name
        self.card_glossary = card_glossary

    def extract(self, episode: EpisodeCandidate, transcript: dict[str, Any]) -> dict[str, Any]:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for live extraction.")
        section = locate_cards_to_watch(transcript.get("segments", []))
        if not section["located"]:
            return {"section": {key: value for key, value in section.items() if key != "segments"}, "recommendations": [], "review_reason": section["review_reason"]}
        from openai import OpenAI
        client = OpenAI()
        evidence = json.dumps(section.pop("segments"), ensure_ascii=False)
        instructions = (
            "Extract only explicit MTG Fast Finance Cards to Watch recommendations from the supplied timestamped section. "
            "Never add finance opinions or infer unsupported cards, printings, speakers, prices, targets, foil status, or confidence. "
            "Unknown values must be null. Preserve original price wording in target.raw. Every pick needs a timestamp and a short evidence excerpt (max 30 words). "
            "Merge duplicate discussion of the same card unless distinct printings are clearly recommended. Mark ambiguity needs_review."
        )
        if self.card_glossary:
            instructions += " Candidate Magic names supplied by the operator for spelling assistance only: " + self.card_glossary
        response = client.responses.create(
            model=self.model_name,
            input=[{"role": "system", "content": instructions}, {"role": "user", "content": evidence}],
            text={"format": {"type": "json_schema", "name": "cards_to_watch", "schema": EXTRACTION_SCHEMA, "strict": True}},
        )
        result = json.loads(response.output_text)
        usage = getattr(response, "usage", None)
        result["_usage"] = usage.model_dump() if hasattr(usage, "model_dump") else (dict(usage) if usage else None)
        result["section"] = section
        if section.get("review_reason") and not result.get("review_reason"):
            result["review_reason"] = section["review_reason"]
        return result


def production_adapters(settings: Settings) -> tuple[Any, Any, Any, Any, Any]:
    return (
        LiveFeedSource(settings.feed_url),
        StreamingDownloader(settings.max_audio_bytes, settings.download_timeout_seconds),
        FfmpegAudioProcessor(settings.audio_chunk_seconds),
        OpenAITranscriber(settings.transcription_model, settings.audio_chunk_seconds),
        OpenAIExtractor(settings.extraction_model, settings.card_glossary),
    )
