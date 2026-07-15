from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import PIPELINE_VERSION, SCHEMA_VERSION
from .rendering import render_episode_markdown
from .utils import atomic_write_json, atomic_write_text, load_json


SYNTHETIC_NOTICE = (
    "All archive content in this Revision 1 build is synthetic fixture data. "
    "It is not real podcast commentary or financial advice."
)


def rebuild_catalog(archive_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    episode_records: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for metadata_path in sorted((archive_dir / "episodes").glob("*/metadata.json")):
        metadata = load_json(metadata_path)
        if not metadata:
            continue
        summary_path = metadata_path.parent / "summary.json"
        summary = load_json(summary_path)
        episode_item = {
            **metadata["episode"],
            "processing_status": metadata["processing"]["status"],
            "review_state": metadata["processing"].get("review_state"),
            "review_reason": metadata["processing"].get("review_reason"),
            "pick_count": len(summary["recommendations"]) if summary else 0,
            "directory": metadata_path.parent.relative_to(archive_dir).as_posix(),
            "outputs": metadata.get("outputs", {}),
        }
        episode_records.append(episode_item)
        if summary:
            for pick in summary["recommendations"]:
                cards.append(
                    {
                        **pick,
                        "episode": {
                            "guid": metadata["episode"]["guid"],
                            "episode_number": metadata["episode"]["episode_number"],
                            "title": metadata["episode"]["title"],
                            "published_at": metadata["episode"]["published_at"],
                            "episode_url": metadata["episode"]["episode_url"],
                            "audio_url": metadata["episode"]["audio_url"],
                        },
                        "processing_status": metadata["processing"]["status"],
                    }
                )
    episode_records.sort(key=lambda item: item["published_at"], reverse=True)
    cards.sort(key=lambda item: (item["episode"]["published_at"], item["start_seconds"] or 0), reverse=True)
    status_counts: dict[str, int] = {}
    for episode in episode_records:
        status = episode["processing_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    counts = {
        "episodes": len(episode_records),
        "picks": len(cards),
        "needs_review": status_counts.get("needs_review", 0),
        "failed": status_counts.get("failed", 0),
        "completed": status_counts.get("complete", 0),
    }
    index = {
        "schema_version": SCHEMA_VERSION,
        "synthetic": True,
        "notice": SYNTHETIC_NOTICE,
        "metadata": {
            "project": "FFW",
            "pipeline_version": PIPELINE_VERSION,
            "generated_from": "synthetic-fixtures",
        },
        "counts": counts,
        "status_counts": status_counts,
        "latest_episode": episode_records[0] if episode_records else None,
        "recent_picks": cards[:6],
        "episodes": episode_records,
    }
    atomic_write_json(archive_dir / "index.json", index)
    atomic_write_json(
        archive_dir / "cards.json",
        {
            "schema_version": SCHEMA_VERSION,
            "synthetic": True,
            "notice": SYNTHETIC_NOTICE,
            "count": len(cards),
            "cards": cards,
        },
    )
    return index, cards


def rerender_archive(archive_dir: Path) -> int:
    rendered = 0
    for summary_path in (archive_dir / "episodes").glob("*/summary.json"):
        summary = load_json(summary_path)
        atomic_write_text(summary_path.with_suffix(".md"), render_episode_markdown(summary))
        rendered += 1
    rebuild_catalog(archive_dir)
    return rendered

