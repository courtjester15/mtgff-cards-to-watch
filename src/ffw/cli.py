from __future__ import annotations

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .archive import rerender_archive
from .config import Settings, VERSION
from .pipeline import Pipeline
from .validation import validate_archive


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ffw", description="FFW pipeline and local archive")
    parser.add_argument("--version", action="version", version=f"FFW {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run the idempotent mocked pipeline")
    run.add_argument("--force", action="store_true", help="Regenerate terminal fixture episodes")
    subparsers.add_parser("validate", help="Validate state, episode outputs, and archive catalogs")
    subparsers.add_parser("render", help="Regenerate Markdown and archive catalogs from JSON")
    backfill = subparsers.add_parser("backfill", help="Regenerate every synthetic fixture")
    backfill.add_argument("--force", action="store_true", default=True, help=argparse.SUPPRESS)
    subparsers.add_parser("process-latest", help="Process only the latest synthetic fixture")
    serve = subparsers.add_parser("serve", help="Serve the repository for the local archive application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _print_results(results: list) -> None:
    for result in results:
        print(f"{result.status:12} {result.guid:28} picks={result.pick_count:2}  {result.message}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings.load()
    if settings.mode != "mock":
        print("Only FFW_MODE=mock is available in Revision 1; production adapters require credentials.")
        return 2
    if args.command == "run":
        _print_results(Pipeline.mock(settings).run(force=args.force))
        return 0
    if args.command == "backfill":
        _print_results(Pipeline.mock(settings).run(force=True))
        return 0
    if args.command == "process-latest":
        _print_results(Pipeline.mock(settings).run(latest_only=True))
        return 0
    if args.command == "render":
        count = rerender_archive(settings.archive_dir)
        print(f"Rendered {count} episode Markdown files and rebuilt archive catalogs.")
        return 0
    if args.command == "validate":
        issues = validate_archive(
            settings.archive_dir,
            settings.state_file,
            settings.root / "schemas/cards-to-watch.schema.json",
        )
        if not issues:
            print("Validation passed with no issues.")
            return 0
        for issue in issues:
            print(f"{issue.severity.upper():7} {issue.code:28} {issue.path}: {issue.message}")
        return 1 if any(issue.severity == "error" for issue in issues) else 0
    if args.command == "serve":
        os.chdir(settings.root)
        handler = partial(SimpleHTTPRequestHandler, directory=str(settings.root))
        server = ThreadingHTTPServer((args.host, args.port), handler)
        print(f"FFW archive: http://{args.host}:{args.port}/web/")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
        finally:
            server.server_close()
        return 0
    return 2
