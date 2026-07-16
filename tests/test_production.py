from __future__ import annotations

import hashlib
import io
import os
import unittest
import uuid
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from ffw.archive import rebuild_catalog
from ffw.detection import locate_cards_to_watch
from ffw.models import EpisodeCandidate
from ffw.config import Settings
from ffw.pipeline import Pipeline
from ffw.production import GeminiExtractor, GeminiTranscriber, OpenAIExtractor, OpenAITranscriber, StreamingDownloader, parse_episode_number, parse_rss, production_adapters
from ffw.state import JsonStateStore
from ffw.utils import atomic_write_json, load_json


def workspace_temp() -> Path:
    path = Path.cwd() / ".test-work" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, *, content_type: str = "audio/mpeg", url: str = "https://cdn.example.test/audio.mp3", length: int | None = None):
        super().__init__(body)
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def episode(url: str = "https://cdn.example.test/audio.mp3") -> EpisodeCandidate:
    return EpisodeCandidate("guid", 42, "Episode 42", "2026-01-01T00:00:00Z", url, "https://example.test/42", [])


class RssTests(unittest.TestCase):
    def test_saved_feed_identity_fallback_order_and_number(self) -> None:
        payload = (Path(__file__).parent / "fixtures/feed.xml").read_bytes()
        items = parse_rss(payload)
        self.assertEqual([1001, 1002, 1003], [item.episode_number for item in items])
        self.assertEqual("real-guid-1001", items[0].guid)
        expected = hashlib.sha256(b"https://cdn.example.test/1002.mp3").hexdigest()
        self.assertEqual(f"enclosure-sha256:{expected}", items[1].guid)
        self.assertEqual(3930, items[2].duration_seconds)
        self.assertEqual(["Host One", "Host Two"], items[2].hosts)

    def test_episode_number_variants(self) -> None:
        self.assertEqual(87, parse_episode_number("Episode #87 — Cards"))
        self.assertEqual(91, parse_episode_number("MTGFF Ep. 91"))
        self.assertEqual(0, parse_episode_number("No number"))

    def test_duplicate_guids_are_collapsed(self) -> None:
        xml = (Path(__file__).parent / "fixtures/feed.xml").read_text(encoding="utf-8")
        duplicate = xml.replace("</channel>", xml[xml.index("<item>"):xml.index("</item>") + 7] + "</channel>")
        self.assertEqual(3, len(parse_rss(duplicate.encode())))


class DownloadTests(unittest.TestCase):
    def test_streams_and_renames_part_file(self) -> None:
        root = workspace_temp()
        downloader = StreamingDownloader(100, 5, opener=lambda *a, **k: FakeResponse(b"audio-data"))
        result = downloader.download(episode(), root / "source-audio")
        self.assertEqual(b"audio-data", result.read_bytes())
        self.assertFalse((root / "source-audio.mp3.part").exists())

    def test_rejects_unsafe_url(self) -> None:
        downloader = StreamingDownloader(100, 5)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            downloader.download(episode("http://example.test/a.mp3"), Path("unused"))

    def test_rejects_mime_and_cleans_part(self) -> None:
        root = workspace_temp()
        downloader = StreamingDownloader(100, 5, opener=lambda *a, **k: FakeResponse(b"html", content_type="text/html"))
        with self.assertRaisesRegex(ValueError, "content type"):
            downloader.download(episode(), root / "source-audio")
        self.assertFalse((root / "source-audio.mp3.part").exists())

    def test_rejects_declared_or_streamed_oversize(self) -> None:
        for response in (FakeResponse(b"x", length=101), FakeResponse(b"x" * 101)):
            with self.subTest(length=response.headers.get("Content-Length")):
                root = workspace_temp()
                downloader = StreamingDownloader(100, 5, opener=lambda *a, response=response, **k: response)
                with self.assertRaisesRegex(ValueError, "maximum size"):
                    downloader.download(episode(), root / "source-audio")


class DetectionAndStateTests(unittest.TestCase):
    def test_section_detection_orders_segments_and_finds_boundaries(self) -> None:
        result = locate_cards_to_watch([
            {"start": 30, "end": 40, "text": "Thanks for listening"},
            {"start": 20, "end": 30, "text": "The card is Example Card"},
            {"start": 10, "end": 20, "text": "Cards to Watch"},
        ])
        self.assertTrue(result["located"])
        self.assertEqual((10, 40, "high"), (result["start_seconds"], result["end_seconds"], result["confidence"]))

    def test_missing_section_never_invents_picks(self) -> None:
        result = locate_cards_to_watch([{"start": 0, "end": 10, "text": "General discussion"}])
        self.assertFalse(result["located"])
        self.assertEqual([], result["segments"])

    def test_discovery_is_idempotent_and_failed_attempt_is_retryable(self) -> None:
        store = JsonStateStore(workspace_temp() / "state.json")
        candidate = episode()
        self.assertTrue(store.discover(candidate))
        self.assertFalse(store.discover(candidate))
        before = len(store.get(candidate.guid)["history"])
        store.transition(candidate.guid, "downloading")
        store.transition(candidate.guid, "failed", error={"stage": "downloading", "message": "boom", "retryable": True})
        self.assertEqual(1, store.get(candidate.guid)["attempt_count"])
        self.assertEqual(before + 2, len(store.get(candidate.guid)["history"]))

    def test_production_catalog_excludes_fixtures_and_reports_health(self) -> None:
        archive = workspace_temp() / "archive"
        for name, synthetic in (("fixture", True), ("real", False)):
            directory = archive / "episodes" / name
            metadata = {
                    "synthetic": synthetic,
                    "episode": {"guid": name, "episode_number": 1, "title": name, "published_at": "2026-01-01T00:00:00Z", "audio_url": "https://example.test/a", "episode_url": "https://example.test/e", "duration_seconds": 1, "hosts": [], "description": None},
                    "processing": {"status": "complete", "processed_at": "2026-01-02T00:00:00Z", "review_state": "approved", "review_reason": None, "error": None},
                    "outputs": {},
            }
            atomic_write_json(directory / "metadata.json", metadata)
            atomic_write_json(directory / "summary.json", {"recommendations": []})
        index, _ = rebuild_catalog(archive, production=True)
        self.assertFalse(index["synthetic"])
        self.assertEqual(["real"], [item["guid"] for item in index["episodes"]])
        self.assertEqual(1, index["metadata"]["real_episode_count"])
        self.assertIn("generated_at", index["metadata"])


class FrontendContractTests(unittest.TestCase):
    def test_pages_paths_and_failure_copy(self) -> None:
        root = Path(__file__).parents[1]
        app = (root / "web/app.js").read_text(encoding="utf-8")
        self.assertIn("fetch(`archive/index.json", app)
        self.assertNotIn("../archive", app)
        self.assertIn("automated pipeline may be updating", app)
        self.assertNotIn("python -m ffw", app)


class ProductionPipelineTests(unittest.TestCase):
    def test_live_provider_selection_is_swappable(self) -> None:
        root = workspace_temp()
        base = {
            "root": root,
            "archive_dir": root / "archive",
            "state_file": root / "state/episodes.json",
            "work_dir": root / ".ffw-work",
            "mode": "live",
        }
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}, clear=False):
            settings = Settings(**base, ai_provider="gemini", transcription_model="gemini-t", extraction_model="gemini-e")
            _, _, _, transcriber, extractor = production_adapters(settings)
            self.assertIsInstance(transcriber, GeminiTranscriber)
            self.assertIsInstance(extractor, GeminiExtractor)
            self.assertEqual(("gemini-t", "gemini-e"), (transcriber.model_name, extractor.model_name))
        settings = Settings(**base, ai_provider="openai", transcription_model="openai-t", extraction_model="openai-e")
        _, _, _, transcriber, extractor = production_adapters(settings)
        self.assertIsInstance(transcriber, OpenAITranscriber)
        self.assertIsInstance(extractor, OpenAIExtractor)

    def test_real_five_pick_publication_cleanup_and_idempotent_skip(self) -> None:
        root = workspace_temp()
        settings = Settings(root, root / "archive", root / "state/episodes.json", root / ".ffw-work", mode="live")
        candidate = episode()

        class Feed:
            def episodes(self): return [candidate]

        class Downloader:
            def download(self, item, destination):
                path = destination.with_suffix(".mp3")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"temporary audio")
                return path

        class Audio:
            def prepare(self, source, destination): return [source]

        class Transcriber:
            model_name = "test-transcriber"
            def transcribe(self, item, files): return {"provider": "test", "segments": [], "chunk_count": 1}

        class Extractor:
            model_name = "test-extractor"
            calls = 0
            def extract(self, item, transcript):
                self.calls += 1
                picks = []
                for index in range(5):
                    picks.append({
                        "card": f"Real Card {index + 1}", "printing": None, "printing_certainty": None,
                        "foil": None, "hosts": [], "recommendation": "Watch for an entry.",
                        "mentioned_price": None, "entry_target": None, "hold": None, "exit_target": None,
                        "reasoning": ["Supply was discussed."], "caveats": [], "confidence": None,
                        "start_seconds": 600 + index * 60, "end_seconds": 630 + index * 60,
                        "evidence_excerpt": f"Short evidence for card {index + 1}.", "review_status": "approved",
                        "review_reason": None,
                    })
                return {"section": {"located": True, "start_seconds": 600, "end_seconds": 930, "label": "Cards to Watch", "confidence": "high", "review_reason": None}, "recommendations": picks, "review_reason": None}

        extractor = Extractor()
        pipeline = Pipeline(settings, Feed(), Downloader(), Audio(), Transcriber(), extractor, JsonStateStore(settings.state_file))
        result = pipeline.run()[0]
        self.assertEqual(("complete", 5), (result.status, result.pick_count))
        summary = load_json(settings.archive_dir / result.output_directory / "summary.json")
        self.assertFalse(summary["synthetic"])
        self.assertEqual(5, len(summary["recommendations"]))
        self.assertFalse(any(settings.work_dir.glob("*")))
        second = pipeline.run()[0]
        self.assertIn("idempotent skip", second.message)
        self.assertEqual(1, extractor.calls)


if __name__ == "__main__":
    unittest.main()
