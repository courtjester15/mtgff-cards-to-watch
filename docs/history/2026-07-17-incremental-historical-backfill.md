# Implementation Brief — Incremental Historical Backfill

**Approved:** 2026-07-17

**Status:** Implemented

**Scope:** FFW processing selection and GitHub Actions workflow control

## Goal

Make each daily scheduled run process the newest eligible episode that has not already been successfully archived. New releases take priority automatically; when none is waiting, the archive progresses backward through history one episode per day.

## Approved behavior

- Preserve the canonical terminal states `complete` and `needs_review`.
- Use durable GUID-keyed episode state as the effective backfill cursor.
- Scan feed metadata newest to oldest, filter durable state first, and apply attempt limits afterward.
- Count selected eligible episodes, never RSS positions, against the live safety cap.
- Provide one selection layer with `next`, `backfill`, `failed_only`, and `exact_guid` policies.
- `next` selects at most one newest unseen or incomplete episode and skips failed records.
- `backfill` selects the newest N unseen or incomplete episodes and skips failed records.
- `failed_only` selects failed records only; it never selects unseen episodes.
- `exact_guid` searches the full fetched feed and bypasses ordinary position and batch selection.
- Skip `complete` and `needs_review` before audio download, transcription, or extraction.
- Treat an empty selection as a successful no-op without rebuilding catalogs, changing generated timestamps, modifying state, or creating a commit.
- Keep scheduled processing at 10:17 UTC with a hard maximum of one attempt.
- Keep manual batches between 1 and 20, defaulting to 1; reject zero, negative, blank, and over-cap values.
- Persist a failed attempt's durable state before the Action reports failure so it cannot block later scheduled progress.
- Report selector and processing statistics in the publish job, and report Pages outcome separately in the deployment job.
- Preserve the archive schema, rendering contract, evidence rules, provider abstraction, temporary-audio policy, existing completed data, and Pages architecture.

## Verification standard

Coverage must prove newest-first selection, terminal and failed skips, failed-only retry, eligible-count limiting, exact GUID lookup, stable GUID behavior under feed reorder, new-release priority followed by historical resumption, safe no-op behavior, and the 1–20 live cap. The complete suite and repeated mock selection must pass before commit.
