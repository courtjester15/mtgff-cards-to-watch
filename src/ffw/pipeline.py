from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .archive import rebuild_catalog
from .config import PIPELINE_VERSION, PROMPT_VERSION, SCHEMA_VERSION, Settings
from .interfaces import AudioDownloader, AudioProcessor, Extractor, FeedSource, Transcriber
from .mocks import MockAudioProcessor, MockDownloader, MockExtractor, MockFeedSource, MockTranscriber
from .models import EpisodeCandidate, PipelineResult, TERMINAL_STATES, utc_now
from .rendering import render_episode_markdown
from .state import JsonStateStore
from .utils import atomic_write_json, atomic_write_text, episode_slug, seconds_to_timestamp, stable_pick_id


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

    def run(self, *, force: bool = False, latest_only: bool = False) -> list[PipelineResult]:
        candidates = self.feed.episodes()
        if latest_only and candidates:
            candidates = [max(candidates, key=lambda episode: episode.published_at)]
        results = [self.process_episode(episode, force=force) for episode in candidates]
        rebuild_catalog(self.settings.archive_dir)
        return results

    def process_episode(self, episode: EpisodeCandidate, *, force: bool = False) -> PipelineResult:
        existing = self.state.get(episode.guid)
        if existing and existing.get("status") in TERMINAL_STATES and not force:
            return PipelineResult(
                guid=episode.guid,
                status=existing["status"],
                output_directory=existing.get("output_directory"),
                pick_count=existing.get("pick_count", 0),
                message="Already processed; idempotent skip.",
            )

        slug = episode_slug(episode.episode_number, episode.title)
        relative_output = f"episodes/{slug}"
        output_dir = self.settings.archive_dir / relative_output
        work_dir = self.settings.work_dir / slug
        work_dir.mkdir(parents=True, exist_ok=True)
        self.state.transition(
            episode.guid,
            "detected",
            title=episode.title,
            episode_number=episode.episode_number,
            published_at=episode.published_at,
            output_directory=relative_output,
            pick_count=0,
            error=None,
        )
        try:
            self.state.transition(episode.guid, "downloading")
            downloaded = self.downloader.download(episode, work_dir / "source.mock-audio")
            self.state.transition(episode.guid, "downloaded")

            prepared_files = self.audio.prepare(downloaded, work_dir / "prepared.mock-audio")
            self.state.transition(episode.guid, "transcribing")
            transcript = self.transcriber.transcribe(episode, prepared_files)
            self.state.transition(episode.guid, "transcribed")

            self.state.transition(episode.guid, "extracting")
            extraction = self.extractor.extract(episode, transcript)
            self.state.transition(episode.guid, "extracted")
            final_status = episode.fixture.get("target_status", "complete")
            if final_status not in {"complete", "needs_review"}:
                final_status = "complete"
            summary = self._build_summary(episode, extraction, final_status)
            metadata = self._build_metadata(episode, final_status, relative_output, summary)
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
                message="Synthetic episode processed.",
            )
        except Exception as exc:
            current = self.state.get(episode.guid) or {}
            failed_stage = current.get("status", "detected")
            self.state.transition(
                episode.guid,
                "failed",
                output_directory=relative_output,
                pick_count=0,
                error={"stage": failed_stage, "message": str(exc), "synthetic": True},
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            metadata = self._build_metadata(episode, "failed", relative_output, None)
            atomic_write_json(output_dir / "metadata.json", metadata)
            return PipelineResult(
                guid=episode.guid,
                status="failed",
                output_directory=relative_output,
                pick_count=0,
                message=str(exc),
            )

    def _processing_metadata(self, episode: EpisodeCandidate, status: str) -> dict[str, Any]:
        state_record = self.state.get(episode.guid) or {}
        return {
            "status": status,
            "review_state": "needs_review" if status == "needs_review" else ("not_applicable" if status == "failed" else "approved"),
            "review_reason": episode.fixture.get("review_reason"),
            "pipeline_version": PIPELINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "transcription_model": self.transcriber.model_name,
            "extraction_model": self.extractor.model_name,
            "prompt_version": PROMPT_VERSION,
            "processed_at": state_record.get("updated_at") or utc_now(),
            "history": state_record.get("history", []),
            "error": state_record.get("error"),
        }

    def _episode_metadata(self, episode: EpisodeCandidate) -> dict[str, Any]:
        return {
            "guid": episode.guid,
            "episode_number": episode.episode_number,
            "title": episode.title,
            "published_at": episode.published_at,
            "audio_url": episode.audio_url,
            "episode_url": episode.episode_url,
            "duration_seconds": episode.fixture.get("duration_seconds"),
            "hosts": episode.hosts,
        }

    def _build_summary(self, episode: EpisodeCandidate, extraction: dict[str, Any], status: str) -> dict[str, Any]:
        recommendations = []
        for source_pick in extraction["recommendations"]:
            pick = deepcopy(source_pick)
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
            "synthetic": True,
            "notice": "Synthetic fixture output. Not real podcast commentary or financial advice.",
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
            "synthetic": True,
            "notice": "Synthetic fixture metadata.",
            "episode": self._episode_metadata(episode),
            "processing": self._processing_metadata(episode, status),
            "outputs": {
                "metadata": f"{relative_output}/metadata.json",
                "summary_json": f"{relative_output}/summary.json" if has_summary else None,
                "summary_markdown": f"{relative_output}/summary.md" if has_summary else None,
            },
        }
