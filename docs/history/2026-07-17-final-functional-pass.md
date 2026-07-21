# 2026-07-17 — ManaIntel Final Functional Pass

## Constraint

ManaIntel receives no more than approximately five additional development hours after the current work. The objective is a small, reliable single-source utility, not continued product expansion. After this pass, development attention moves to ManaSpec adoption and GalleyFlow.

## Required outcome

ManaIntel should:

1. Run automatically and continue historical backfill from durable state.
2. Apply attempt limits after eligibility filtering.
3. Retry failed episodes only when explicitly requested and retry one exact episode when identified.
4. Leave files and deployment state alone on a true no-op.
5. Present compact, readable Cards to Watch summaries and understandable failures.
6. Let Jason correct, add, or exclude picks without editing generated archive files.
7. Preserve original extraction and store manual corrections as a separate durable override.
8. Open remote RSS audio at or near a pick timestamp without storing podcast audio.

## Final-pass order

### 1. Pipeline reliability

- Keep the state-aware selector as the single eligibility boundary.
- Load feed and durable state, filter by run mode, sort deterministically, then apply the attempt limit.
- Normal runs skip successful terminal records and failed records.
- Backfill selects historical unseen/nonterminal records predictably.
- Failed-only retry selects only durable failed records.
- Exact episode processing searches the full fetched feed.
- Empty selection must not rebuild catalogs, change timestamps, create commits, or trigger Pages deployment.

Eligibility-first selection, failed-only selection, exact-GUID selection, and pipeline-level no-op behavior were implemented before this note. The deployment-level no-op guard still requires verification.

### 2. Status and readability

The UI should communicate: Unseen, Processing, Completed, Completed — Needs Review, Reviewed, Manually Corrected, Failed, Skipped, and Excluded. Internal pipeline enums may remain simpler.

Failures should expose a short category, message, last attempt, attempt count, retryability, and manual-review need. Categories may include feed metadata, missing audio URL, download, transcription, section detection/boundary, structured extraction, invalid extraction, archive generation, and unknown processing errors. Raw technical detail stays collapsed.

Pick cards prioritize card name, printing/finish, host, recommendation, mentioned/target price, short summary, timestamp, evidence-based warning, and review state. Empty fields are omitted and evidence/debug text stays secondary.

### 3. Manual review overrides

The Review UI supports updating, adding, confirming, and excluding picks; marking the episode reviewed; saving a correction payload; and cancelling without changes. Because GitHub Pages is static, the bounded implementation copies or downloads JSON for placement at:

`data/reviews/<episode-id>.json`

Original extraction is immutable source data. Effective display is:

`original extraction + validated manual override = effective reviewed result`

Review files are durable input and must never be removed by cleanup or overwritten by rendering/backfill.

Example shape:

```json
{
  "episode_id": "stable-episode-id",
  "reviewed_at": "2026-07-17T00:00:00Z",
  "reviewed_by": "manual",
  "status": "corrected",
  "pick_overrides": [
    {
      "source_pick_id": "original-pick-id",
      "action": "update",
      "fields": {
        "card_name": "Corrected Card",
        "timestamp_seconds": 1842
      }
    },
    {
      "action": "add",
      "fields": {
        "card_name": "Missing Card",
        "summary": "Manually added pick"
      }
    },
    {
      "source_pick_id": "false-pick-id",
      "action": "exclude"
    }
  ]
}
```

### 4. Timestamp playback

Use an in-page HTML audio player backed by the RSS enclosure URL. A timestamp link carries `t=<seconds>`; after `loadedmetadata`, JavaScript seeks to that time and attempts playback. The player includes play/pause, seek, duration, ±15 seconds, selected timestamp, loading/error feedback, and the original episode link. Autoplay denial, missing/redirected URLs, and hosts without byte-range support must fail to a useful source link. Audio is never copied into the repository.

### 5. Single-episode retry

The backend continues to support an exact GUID, currently:

```bash
python -m ffw run --live --force-guid <rss-guid>
```

The static UI should show the episode GUID and offer a copyable command/workflow input. It must not embed credentials or attempt an unauthenticated workflow write.

## Explicitly out of scope

React or design-system conversion; rich animation; additional sources; source-agnostic migration work; accounts; hosted databases; authenticated browser editing; mobile-first redesign; analytics; prices, scoring, or portfolio integration; diarization overhaul; full transcript editing; audio hosting; alerts; sharing; and unrelated refactors.

## Stop rule

Once the definition in `docs/ROADMAP.md` is met—or the five-hour budget is exhausted—stop feature development. Only a real production failure that prevents the basic utility should reopen ManaIntel work.
