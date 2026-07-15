from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


TERMINAL_STATES = {"complete", "needs_review", "failed"}
PROCESSING_STATES = {
    "detected",
    "downloading",
    "downloaded",
    "transcribing",
    "transcribed",
    "extracting",
    "extracted",
    "needs_review",
    "complete",
    "failed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EpisodeCandidate:
    guid: str
    episode_number: int
    title: str
    published_at: str
    audio_url: str
    episode_url: str
    hosts: list[str]
    fixture: dict[str, Any] = field(repr=False, compare=False)


@dataclass
class PipelineResult:
    guid: str
    status: str
    output_directory: str | None = None
    pick_count: int = 0
    message: str = ""

