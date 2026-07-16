from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.2.0"
PIPELINE_VERSION = "0.2.0"
SCHEMA_VERSION = "1.1.0"
PROMPT_VERSION = "cards-to-watch-v2"
MOCK_TRANSCRIPTION_MODEL = "mock-transcriber-v1"
MOCK_EXTRACTION_MODEL = "mock-extractor-v1"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root: Path
    archive_dir: Path
    state_file: Path
    work_dir: Path
    mode: str = "mock"
    feed_url: str = "https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss"
    feed_name: str = "MTG Fast Finance"
    max_audio_bytes: int = 250_000_000
    download_timeout_seconds: int = 120
    audio_chunk_seconds: int = 1200
    transcription_model: str = "gpt-4o-transcribe-diarize"
    extraction_model: str = "gpt-5.6-luna"
    card_glossary: str = ""
    repository_url: str = "https://github.com/courtjester15/mtgff-cards-to-watch"

    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        root = (root or project_root()).resolve()
        archive = root / os.getenv("FFW_ARCHIVE_DIR", "archive")
        state = root / os.getenv("FFW_STATE_FILE", "state/episodes.json")
        return cls(
            root=root,
            archive_dir=archive,
            state_file=state,
            work_dir=root / ".ffw-work",
            mode=os.getenv("FFW_MODE", "mock"),
            feed_url=os.getenv("FFW_FEED_URL", "https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss"),
            feed_name=os.getenv("FFW_FEED_NAME", "MTG Fast Finance"),
            max_audio_bytes=int(os.getenv("FFW_MAX_AUDIO_BYTES", "250000000")),
            download_timeout_seconds=int(os.getenv("FFW_DOWNLOAD_TIMEOUT_SECONDS", "120")),
            audio_chunk_seconds=int(os.getenv("FFW_AUDIO_CHUNK_SECONDS", "1200")),
            transcription_model=os.getenv("FFW_TRANSCRIPTION_MODEL", "gpt-4o-transcribe-diarize"),
            extraction_model=os.getenv("FFW_EXTRACTION_MODEL", "gpt-5.6-luna"),
            card_glossary=os.getenv("FFW_CARD_GLOSSARY", ""),
            repository_url=os.getenv("FFW_REPOSITORY_URL", "https://github.com/courtjester15/mtgff-cards-to-watch"),
        )
