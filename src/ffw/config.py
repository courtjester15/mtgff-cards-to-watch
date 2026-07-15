from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.1.0"
PIPELINE_VERSION = "0.1.0-mock"
SCHEMA_VERSION = "1.0.0"
PROMPT_VERSION = "cards-to-watch-v1"
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
        )

