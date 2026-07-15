from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import PROCESSING_STATES
from .rendering import render_episode_markdown
from .utils import load_json, stable_pick_id


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    path: str
    message: str


def validate_archive(archive_dir: Path, state_file: Path, schema_path: Path | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    index = load_json(archive_dir / "index.json")
    cards_payload = load_json(archive_dir / "cards.json")
    if not index:
        return [ValidationIssue("error", "missing_index", str(archive_dir / "index.json"), "Archive index is missing.")]
    if not cards_payload:
        issues.append(ValidationIssue("error", "missing_cards", str(archive_dir / "cards.json"), "Flattened cards catalog is missing."))
        cards_payload = {"cards": []}
    if schema_path is not None:
        schema = load_json(schema_path)
        if not schema:
            issues.append(ValidationIssue("error", "missing_schema", str(schema_path), "Versioned JSON Schema is missing or invalid."))
        elif schema.get("properties", {}).get("schema_version", {}).get("const") != index.get("schema_version"):
            issues.append(ValidationIssue("error", "schema_version_drift", str(schema_path), "Schema const does not match archive schema version."))

    seen_guids: set[str] = set()
    seen_pick_ids: set[str] = set()
    all_summary_ids: set[str] = set()
    for episode in index.get("episodes", []):
        guid = episode.get("guid")
        episode_path = archive_dir / episode["directory"]
        if not guid:
            issues.append(ValidationIssue("error", "missing_guid", str(episode_path), "Episode GUID is required."))
        elif guid in seen_guids:
            issues.append(ValidationIssue("error", "duplicate_guid", str(episode_path), f"Duplicate GUID: {guid}"))
        seen_guids.add(guid)
        status = episode.get("processing_status")
        if status not in PROCESSING_STATES:
            issues.append(ValidationIssue("error", "invalid_state", str(episode_path), f"Unknown state: {status}"))
        metadata_path = episode_path / "metadata.json"
        summary_path = episode_path / "summary.json"
        markdown_path = episode_path / "summary.md"
        if not metadata_path.exists():
            issues.append(ValidationIssue("error", "missing_metadata", str(metadata_path), "Episode metadata is required."))
        if status in {"complete", "needs_review"} and (not summary_path.exists() or not markdown_path.exists()):
            issues.append(ValidationIssue("error", "completed_without_outputs", str(episode_path), "Terminal successful episode is missing outputs."))
            continue
        if status == "failed":
            continue
        summary = load_json(summary_path)
        if not summary:
            continue
        required_summary_fields = {"schema_version", "synthetic", "notice", "episode", "processing", "section", "recommendations"}
        missing_summary_fields = required_summary_fields - set(summary)
        if missing_summary_fields:
            issues.append(ValidationIssue("error", "summary_schema", str(summary_path), f"Missing summary fields: {sorted(missing_summary_fields)}"))
        if summary.get("schema_version") != index.get("schema_version"):
            issues.append(ValidationIssue("error", "summary_schema_version", str(summary_path), "Summary schema version does not match index."))
        if summary.get("episode", {}).get("guid") != guid:
            issues.append(ValidationIssue("error", "episode_identity_drift", str(summary_path), "Summary GUID does not match catalog identity."))
        expected_markdown = render_episode_markdown(summary)
        actual_markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
        if expected_markdown != actual_markdown:
            issues.append(ValidationIssue("error", "markdown_drift", str(markdown_path), "Markdown was not rendered from current JSON."))
        episode_pick_keys: set[tuple[Any, ...]] = set()
        for pick in summary.get("recommendations", []):
            pick_path = f"{summary_path}#{pick.get('id', 'unknown')}"
            required_pick_fields = {
                "id", "card", "printing", "printing_certainty", "hosts", "recommendation", "entry_target",
                "hold", "exit_target", "reasoning", "caveats", "confidence", "start_seconds", "end_seconds",
                "timestamp", "evidence_excerpt", "review_status", "listen_url",
            }
            missing_pick_fields = required_pick_fields - set(pick)
            if missing_pick_fields:
                issues.append(ValidationIssue("error", "pick_schema", pick_path, f"Missing pick fields: {sorted(missing_pick_fields)}"))
            expected_id = stable_pick_id(guid, pick.get("card", ""), pick.get("start_seconds"), pick.get("printing"))
            if pick.get("id") != expected_id:
                issues.append(ValidationIssue("error", "unstable_pick_id", pick_path, "Pick ID does not match its stable identity."))
            if pick.get("id") in seen_pick_ids:
                issues.append(ValidationIssue("error", "duplicate_pick_id", pick_path, "Pick ID appears more than once."))
            seen_pick_ids.add(pick.get("id"))
            all_summary_ids.add(pick.get("id"))
            duplicate_key = (pick.get("card", "").casefold(), pick.get("printing"), pick.get("start_seconds"))
            if duplicate_key in episode_pick_keys:
                issues.append(ValidationIssue("error", "duplicate_recommendation", pick_path, "Duplicate recommendation within episode."))
            episode_pick_keys.add(duplicate_key)
            if not pick.get("card") or not pick.get("recommendation"):
                issues.append(ValidationIssue("error", "missing_required_pick_field", pick_path, "Card and recommendation are required."))
            if not pick.get("evidence_excerpt") or pick.get("start_seconds") is None:
                issues.append(ValidationIssue("error", "missing_evidence", pick_path, "Evidence excerpt and timestamp are required."))
            for target_name in ("entry_target", "exit_target"):
                target = pick.get(target_name)
                if target is not None and not target.get("raw"):
                    issues.append(ValidationIssue("error", "target_without_source_text", pick_path, f"{target_name} requires raw source wording."))
            certainty = pick.get("printing_certainty")
            if certainty not in {None, "confirmed", "likely", "ambiguous"}:
                issues.append(ValidationIssue("error", "invalid_printing_certainty", pick_path, f"Invalid printing certainty: {certainty}"))
            confidence = pick.get("confidence")
            if confidence not in {None, "low", "medium", "high"}:
                issues.append(ValidationIssue("error", "invalid_confidence", pick_path, f"Invalid confidence: {confidence}"))

    flattened_ids = {pick.get("id") for pick in cards_payload.get("cards", [])}
    if flattened_ids != all_summary_ids:
        issues.append(ValidationIssue("error", "cards_catalog_drift", str(archive_dir / "cards.json"), "Flattened cards do not match episode summaries."))
    if index.get("counts", {}).get("picks") != len(all_summary_ids):
        issues.append(ValidationIssue("error", "count_mismatch", str(archive_dir / "index.json"), "Index pick count is incorrect."))

    state = load_json(state_file, {"episodes": {}})
    state_guids = set(state.get("episodes", {}))
    if state_guids != seen_guids:
        issues.append(ValidationIssue("error", "state_catalog_drift", str(state_file), "State GUIDs do not match archive episodes."))
    return issues
