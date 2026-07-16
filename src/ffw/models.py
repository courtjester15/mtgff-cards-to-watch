from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


TERMINAL_STATES = {"complete", "needs_review"}
PROCESSING_STATES = {
    "detected",
    "queued",
    "downloading",
    "downloaded",
    "preparing",
    "transcribing",
    "transcribed",
    "extracting",
    "extracted",
    "validating",
    "publishing",
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
    description: str | None = None
    duration_seconds: int | None = None
    feed_metadata: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    fixture: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def synthetic(self) -> bool:
        return bool(self.fixture)


@dataclass
class PipelineResult:
    guid: str
    status: str
    output_directory: str | None = None
    pick_count: int = 0
    message: str = ""
