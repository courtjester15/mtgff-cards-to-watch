from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .models import EpisodeCandidate


class FeedSource(Protocol):
    def episodes(self) -> list[EpisodeCandidate]: ...


class AudioDownloader(Protocol):
    def download(self, episode: EpisodeCandidate, destination: Path) -> Path: ...


class AudioProcessor(Protocol):
    def prepare(self, source: Path, destination: Path) -> list[Path]: ...


class Transcriber(Protocol):
    model_name: str

    def transcribe(self, episode: EpisodeCandidate, audio_files: list[Path]) -> dict[str, Any]: ...


class Extractor(Protocol):
    model_name: str

    def extract(self, episode: EpisodeCandidate, transcript: dict[str, Any]) -> dict[str, Any]: ...


class StateStore(Protocol):
    def get(self, guid: str) -> dict[str, Any] | None: ...

    def transition(self, guid: str, status: str, **updates: Any) -> None: ...

