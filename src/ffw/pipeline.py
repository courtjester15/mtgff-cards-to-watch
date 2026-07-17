from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
import os
from typing import Any

from .archive import rebuild_catalog
from .config import PIPELINE_VERSION, PROMPT_VERSION, SCHEMA_VERSION, Settings
from .interfaces import AudioDownloader, AudioProcessor, Extractor, FeedSource, Transcriber
from .mocks import MockAudioProcessor, MockDownloader, MockExtractor, MockFeedSource, MockTranscriber
from .models import EpisodeCandidate, PipelineResult, TERMINAL_STATES, utc_now
from .production import production_adapters
from .rendering import render_episode_markdown
from .state import JsonStateStore
from .utils import atomic_write_json, atomic_write_text, episode_slug, seconds_to_timestamp, stable_pick_id

PROVIDER_WIDE_ERROR_PATTERNS = (
    "401",
    "403",
    "429",
    "api key",
    "invalid api",
    "invalid_argument",
    "not_found",
    "permission_denied",
    "quota",
    "rate limit",
    "resource_exhausted",
    "response_json_schema",
    "response_schema",
    "unauthenticated",
    "unsupported model",
)


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        feed: FeedSource,
        downloader: AudioDownloader,
        audio: AudioProcessor,
        transcriber: Transcriber,
        extractor: Extractor,
        state: JsonStateStore,
    ) -> None:
        self.settings = settings
        self.feed = feed
        self.downloader = downloader
        self.audio = audio
        self.transcriber = transcriber
        self.extractor = extractor
        self.state = state

    @classmethod
    def mock(cls, settings: Settings) -> "Pipeline":
        return cls(
            settings=settings,
            feed=MockFeedSource(),
            downloader=MockDownloader(),
            audio=MockAudioProcessor(),
            transcriber=MockTranscriber(),
            extractor=MockExtractor(),
            state=JsonStateStore(settings.state_file),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "Pipeline":
        if settings.mode == "mock":
            return cls.mock(settings)
        if settings.mode != "live":
            raise ValueError("FFW_MODE must be 'mock' or 'live'.")
        if settings.ai_provider == "gemini":
            if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
                raise RuntimeError("GEMINI_API_KEY is required before a Gemini live pipeline run can start.")
        elif settings.ai_provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY is required before an OpenAI live pipeline run can start.")
        else:
            raise ValueError("FFW_AI_PROVIDER must be 'openai' or 'gemini'.")
        feed, downloader, audio, transcriber, extractor = production_adapters(settings)
        return cls(settings, feed, downloader, audio, transcriber, extractor, JsonStateStore(settings.state_file))

    def run(
        self, *, force: bool = False, latest_only: bool = False, limit: int | None = None,
        retry_failed: bool = False, force_guid: str | None = None,
    ) -> list[PipelineResult]:
        self._validate_live_scope(latest_only=latest_only, limit=limit, force_guid=force_guid)
        candidates = self.feed.episodes()
        if latest_only and candidates:
            candidates = [max(candidates, key=lambda episode: episode.published_at)]
        if limit is not None:
            candidates = sorted(candidates, key=lambda episode: episode.published_at, reverse=True)[:limit]
            candidates.sort(key=lambda episode: episode.published_at)
        if force_guid:
            candidates = [episode for episode in candidates if episode.guid == force_guid]
        results: list[PipelineResult] = []
        for episode in candidates:
            self.state.discover(episode)
            result = self.process_episode(episode, force=force, retry_failed=retry_failed)
            results.append(result)
            if self.settings.mode == "live" and result.status == "failed" and self._is_provider_wide_error(result.message):
                break
        rebuild_catalog(
            self.settings.archive_dir,
            production=self.settings.mode == "live",
            feed_name=self.settings.feed_name,
            repository_url=self.settings.repository_url,
        )
        return results

    def _validate_live_scope(self, *, latest_only: bool, limit: int | None, force_guid: str | None) -> None:
        if self.settings.mode != "live" or latest_only or force_guid:
            return
        if limit is None:
            raise ValueError("Live runs require a positive --limit to avoid processing the full feed.")
        if limit < 1:
            raise ValueError("Live run --limit must be at least 1.")
        if limit > self.settings.max_live_batch:
            raise ValueError(f"Live run --limit cannot exceed {self.settings.max_live_batch}.")

    @staticmethod
    def _is_provider_wide_error(message: str) -> bool:
        normalized = message.lower()
        return any(pattern in normalized for pattern in PROVIDER_WIDE_ERROR_PATTERNS)

    def process_episode(self, episode: EpisodeCandidate, *, force: bool = False, retry_failed: bool = False) -> PipelineResult:
        existing = self.state.get(episode.guid)
        should_skip_failed = existing and existing.get("status") == "failed" and (episode.synthetic or not retry_failed)
        if existing and (existing.get("status") in TERMINAL_STATES or should_skip_failed) and not force:
            return PipelineResult(
                guid=episode.guid,
                status=existing["status"],
                output_directory=existing.get("output_directory"),
                pick_count=existing.get("pick_count", 0),
                message="Already processed; idempotent skip.",
            )

        slug = episode_slug(episode.episode_number, episode.title, episode.guid)
        relative_output = f"episodes/{slug}"
        output_dir = self.settings.archive_dir / relative_output
        work_dir = self.settings.work_dir / slug
        work_dir.mkdir(parents=True, exist_ok=True)
        if not existing:
            self.state.discover(episode)
            existing = self.state.get(episode.guid)
        if existing.get("status") != "queued" or not existing.get("output_directory"):
            self.state.transition(episode.guid, "queued", output_directory=relative_output, pick_count=0, error=None)
        try:
            self.state.transition(episode.guid, "downloading")
            downloaded = self.downloader.download(episode, work_dir / "source-audio")
            self.state.transition(episode.guid, "downloaded")

            self.state.transition(episode.guid, "preparing")
            prepared_files = self.audio.prepare(downloaded, work_dir / "prepared-audio")
            self.state.transition(episode.guid, "transcribing")
            transcript = self.transcriber.transcribe(episode, prepared_files)
            self.state.transition(episode.guid, "transcribed", transcription={
                "provider": transcript.get("provider", "mock"), "model": self.transcriber.model_name,
                "chunk_count": transcript.get("chunk_count", len(prepared_files)),
                "duration_seconds": transcript.get("duration_seconds", episode.duration_seconds),
                "usage": transcript.get("usage"),
            })

            self.state.transition(episode.guid, "extracting")
            extraction = self.extractor.extract(episode, transcript)
            extraction_usage = extraction.pop("_usage", None)
            self.state.transition(episode.guid, "extracted", extraction_usage=extraction_usage)
            final_status = episode.fixture.get("target_status", "complete") if episode.synthetic else (
                "needs_review" if extraction.get("review_reason") or not extraction.get("recommendations")
                or any(pick.get("review_status") != "approved" for pick in extraction.get("recommendations", []))
                else "complete"
            )
            if final_status not in {"complete", "needs_review"}:
                final_status = "complete"
            summary = self._build_summary(episode, extraction, final_status)
            metadata = self._build_metadata(episode, final_status, relative_output, summary)
            self.state.transition(episode.guid, "validating")
            self._validate_before_publish(summary)
            self.state.transition(episode.guid, "publishing")
            output_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(output_dir / "metadata.json", metadata)
            atomic_write_json(output_dir / "summary.json", summary)
            atomic_write_text(output_dir / "summary.md", render_episode_markdown(summary))
            self.state.transition(
                episode.guid,
                final_status,
                output_directory=relative_output,
                pick_count=len(summary["recommendations"]),
                review_reason=extraction.get("review_reason"),
                error=None,
            )
            # Refresh durable outputs after the final transition so their audit history is complete.
            summary["processing"] = self._processing_metadata(episode, final_status)
            atomic_write_json(output_dir / "summary.json", summary)
            atomic_write_text(output_dir / "summary.md", render_episode_markdown(summary))
            metadata = self._build_metadata(episode, final_status, relative_output, summary)
            atomic_write_json(output_dir / "metadata.json", metadata)
            return PipelineResult(
                guid=episode.guid,
                status=final_status,
                output_directory=relative_output,
                pick_count=len(summary["recommendations"]),
                message="Synthetic episode processed." if episode.synthetic else "Live episode processed.",
            )
        except Exception as exc:
            current = self.state.get(episode.guid) or {}
            failed_stage = current.get("status", "detected")
            retryable = not episode.synthetic and not self._is_provider_wide_error(str(exc))
            self.state.transition(
                episode.guid,
                "failed",
                output_directory=relative_output,
                pick_count=0,
                error={"stage": failed_stage, "message": str(exc), "synthetic": episode.synthetic, "retryable": retryable},
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            metadata = self._build_metadata(episode, "failed", relative_output, None)
            (output_dir / "summary.json").unlink(missing_ok=True)
            (output_dir / "summary.md").unlink(missing_ok=True)
            atomic_write_json(output_dir / "metadata.json", metadata)
            return PipelineResult(
                guid=episode.guid,
                status="failed",
                output_directory=relative_output,
                pick_count=0,
                message=str(exc),
            )
        finally:
            if not episode.synthetic:
                shutil.rmtree(work_dir, ignore_errors=True)

    @staticmethod
    def _validate_before_publish(summary: dict[str, Any]) -> None:
        for pick in summary.get("recommendations", []):
            if not pick.get("card") or not pick.get("recommendation"):
                raise ValueError("Extraction contains a pick without card and recommendation text.")
            if pick.get("start_seconds") is None or not pick.get("evidence_excerpt"):
                raise ValueError("Every published pick requires a timestamp and compact evidence.")

    def _processing_metadata(self, episode: EpisodeCandidate, status: str) -> dict[str, Any]:
        state_record = self.state.get(episode.guid) or {}
        return {
            "status": status,
            "review_state": "needs_review" if status == "needs_review" else ("not_applicable" if status == "failed" else "approved"),
            "review_reason": state_record.get("review_reason") or episode.fixture.get("review_reason"),
            "pipeline_version": PIPELINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "transcription_model": self.transcriber.model_name,
            "extraction_model": self.extractor.model_name,
            "prompt_version": PROMPT_VERSION,
            "processed_at": state_record.get("updated_at") or utc_now(),
            "history": state_record.get("history", []),
            "error": state_record.get("error"),
            "transcription": state_record.get("transcription"),
            "extraction_usage": state_record.get("extraction_usage"),
        }

    def _episode_metadata(self, episode: EpisodeCandidate) -> dict[str, Any]:
        return {
            "guid": episode.guid,
            "episode_number": episode.episode_number,
            "title": episode.title,
            "published_at": episode.published_at,
            "audio_url": episode.audio_url,
            "episode_url": episode.episode_url,
            "duration_seconds": episode.duration_seconds if episode.duration_seconds is not None else episode.fixture.get("duration_seconds"),
            "hosts": episode.hosts,
            "description": episode.description,
        }

    def _build_summary(self, episode: EpisodeCandidate, extraction: dict[str, Any], status: str) -> dict[str, Any]:
        recommendations = []
        for source_pick in extraction["recommendations"]:
            pick = deepcopy(source_pick)
            pick.setdefault("foil", None)
            pick.setdefault("mentioned_price", None)
            pick.setdefault("review_reason", None)
            pick["id"] = stable_pick_id(
                episode.guid,
                pick["card"],
                pick.get("start_seconds"),
                pick.get("printing"),
            )
            pick["timestamp"] = seconds_to_timestamp(pick.get("start_seconds"))
            pick["listen_url"] = f"{episode.audio_url}#t={pick['start_seconds']}" if pick.get("start_seconds") is not None else episode.audio_url
            recommendations.append(pick)
        return {
            "schema_version": SCHEMA_VERSION,
            "synthetic": episode.synthetic,
            "notice": "Synthetic fixture output. Not real podcast commentary or financial advice." if episode.synthetic else "Automated transcription and extraction; verify against the linked source audio.",
            "episode": self._episode_metadata(episode),
            "processing": self._processing_metadata(episode, status),
            "section": extraction["section"],
            "recommendations": recommendations,
        }

    def _build_metadata(
        self,
        episode: EpisodeCandidate,
        status: str,
        relative_output: str,
        summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        has_summary = summary is not None
        return {
            "schema_version": SCHEMA_VERSION,
            "synthetic": episode.synthetic,
            "notice": "Synthetic fixture metadata." if episode.synthetic else "Live automated pipeline metadata.",
            "episode": self._episode_metadata(episode),
            "processing": self._processing_metadata(episode, status),
            "outputs": {
                "metadata": f"{relative_output}/metadata.json",
                "summary_json": f"{relative_output}/summary.json" if has_summary else None,
                "summary_markdown": f"{relative_output}/summary.md" if has_summary else None,
            },
        }
