# FFW — MTG Fast Finance Cards to Watch

FFW is a standalone personal utility composed of two decoupled products:

1. A Python automation pipeline that turns podcast episodes into validated, versioned JSON and Markdown.
2. A static vanilla JavaScript archive that reads only the generated JSON.

Revision 1 is a complete credential-free foundation. It includes production-shaped interfaces and a fully runnable mocked pipeline, but it does **not** contact a live RSS feed, download real audio, or call OpenAI.

> All recommendations, quotations, prices, episode numbers, people, and processing outcomes currently in `archive/` are synthetic fixtures. They are not real podcast commentary or financial advice.

## Quick start

Python 3.11 or newer is required. No third-party runtime dependencies or downloads are needed.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e . --no-deps --no-build-isolation
python -m ffw run
python -m ffw validate
python -m ffw serve
```

Open <http://127.0.0.1:8765/web/>. Stop the server with `Ctrl+C`.

On macOS or Linux, activate with `source .venv/bin/activate`; the remaining commands are identical.

For development without installing the package, set `PYTHONPATH=src` before invoking `python -m ffw`.

## Commands

| Command | Purpose |
|---|---|
| `python -m ffw run` | Process unprocessed mock episodes and skip terminal records idempotently. |
| `python -m ffw validate` | Validate identity, states, evidence, outputs, catalogs, and deterministic Markdown. |
| `python -m ffw render` | Re-render Markdown from JSON and rebuild `index.json` and `cards.json`. |
| `python -m ffw serve` | Serve the repository and local archive on port 8765. |
| `python -m ffw backfill` | Force-regenerate every synthetic fixture. |
| `python -m ffw process-latest` | Process only the newest synthetic fixture. |

Run the tests with:

```powershell
python -m unittest discover -s tests -v
```

## Generated archive

```text
archive/
├── index.json                 # frontend master catalog
├── cards.json                 # flattened searchable recommendations
└── episodes/
    └── 0901-fetchland-signals/
        ├── metadata.json      # identity, audit metadata, state history
        ├── summary.json       # canonical Cards to Watch data
        └── summary.md         # deterministic rendering of summary.json
```

A deliberately failed fixture receives `metadata.json` but no summary files. Successful and needs-review episodes always receive all three outputs.

## Trust rules

- Unknown means `null`; it is never silently inferred.
- An entry or exit target must preserve the source wording in `raw`.
- Every pick requires a timestamp and evidence excerpt.
- Ambiguity is surfaced through certainty and review state.
- Markdown is generated from JSON, never independently.
- Pick identifiers are deterministic and insensitive to list ordering.
- Raw audio is temporary and is never part of the archive contract.

Structural validation can prove that evidence exists; it cannot prove that an AI interpreted speech faithfully. Production readiness therefore requires representative extraction evaluations and explicit review thresholds.

## Current boundary

Production-ready foundation:

- Package, CLI, state model, pipeline orchestration, rendering, catalogs, validation, tests, and local UI.
- Protocols for feed, downloader, audio, transcription, extraction, and state adapters.
- Idempotent terminal-state handling and auditable processing histories.
- Versioned JSON Schema and pipeline metadata.

Mocked or intentionally disabled:

- Live SoundCloud RSS, network download, `ffmpeg`, OpenAI transcription, model extraction, and credential handling.
- GitHub Actions, GitHub Pages, notifications, databases, price tracking, and ManaSpec integration.

See [Product Spec](docs/PRODUCT_SPEC.md), [Architecture](docs/ARCHITECTURE.md), [Data Model](docs/DATA_MODEL.md), and [Decisions](docs/DECISIONS.md).
