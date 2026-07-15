from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from .config import MOCK_EXTRACTION_MODEL, MOCK_TRANSCRIPTION_MODEL
from .models import EpisodeCandidate
from .utils import atomic_write_text


def load_fixture_bundle() -> dict[str, Any]:
    fixture_path = files("ffw").joinpath("fixtures/episodes.json")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


class MockFeedSource:
    def __init__(self, bundle: dict[str, Any] | None = None) -> None:
        self.bundle = bundle or load_fixture_bundle()

    def episodes(self) -> list[EpisodeCandidate]:
        episodes = []
        for item in self.bundle["episodes"]:
            episodes.append(
                EpisodeCandidate(
                    guid=item["guid"],
                    episode_number=item["episode_number"],
                    title=item["title"],
                    published_at=item["published_at"],
                    audio_url=item["audio_url"],
                    episode_url=item["episode_url"],
                    hosts=item["hosts"],
                    fixture=item,
                )
            )
        return sorted(episodes, key=lambda episode: episode.published_at)


class MockDownloader:
    def download(self, episode: EpisodeCandidate, destination: Path) -> Path:
        if episode.fixture.get("failure_stage") == "downloading":
            raise RuntimeError(episode.fixture.get("failure_message", "Synthetic download failure"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            destination,
            "FFW synthetic audio placeholder. This is not an MP3 and contains no real podcast audio.\n",
        )
        return destination


class MockAudioProcessor:
    def prepare(self, source: Path, destination: Path) -> list[Path]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(destination, source.read_text(encoding="utf-8"))
        return [destination]


class MockTranscriber:
    model_name = MOCK_TRANSCRIPTION_MODEL

    def transcribe(self, episode: EpisodeCandidate, audio_files: list[Path]) -> dict[str, Any]:
        if episode.fixture.get("failure_stage") == "transcribing":
            raise RuntimeError(episode.fixture.get("failure_message", "Synthetic transcription failure"))
        return {
            "synthetic": True,
            "text": episode.fixture.get("mock_transcript") or "",
            "segments": [],
            "source_files": [path.name for path in audio_files],
        }


class MockExtractor:
    model_name = MOCK_EXTRACTION_MODEL

    def extract(self, episode: EpisodeCandidate, transcript: dict[str, Any]) -> dict[str, Any]:
        if episode.fixture.get("failure_stage") == "extracting":
            raise RuntimeError(episode.fixture.get("failure_message", "Synthetic extraction failure"))
        return {
            "section": {
                "located": bool(episode.fixture.get("recommendations")),
                "start_seconds": min(
                    (pick["start_seconds"] for pick in episode.fixture.get("recommendations", [])),
                    default=None,
                ),
                "end_seconds": max(
                    (pick["end_seconds"] for pick in episode.fixture.get("recommendations", [])),
                    default=None,
                ),
                "label": "Cards to Watch",
            },
            "recommendations": episode.fixture.get("recommendations", []),
            "review_reason": episode.fixture.get("review_reason"),
        }


class ProductionIntegrationRequired(RuntimeError):
    """Raised by intentionally unconfigured production adapters."""


class LiveFeedSource:
    def episodes(self) -> list[EpisodeCandidate]:
        raise ProductionIntegrationRequired("Live RSS is scaffolded but intentionally not implemented in Revision 1.")


class LiveTranscriber:
    model_name = "unconfigured"

    def transcribe(self, episode: EpisodeCandidate, audio_files: list[Path]) -> dict[str, Any]:
        raise ProductionIntegrationRequired("OpenAI transcription requires production credentials and is not enabled.")

