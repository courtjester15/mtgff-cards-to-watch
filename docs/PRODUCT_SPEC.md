# FFW Product Specification

## Purpose

FFW eliminates the recurring manual work required to capture the **Cards to Watch** section of MTG Fast Finance. It deliberately excludes whole-episode summaries and original finance opinions.

Revision 1 proves the architecture with synthetic input and no production credentials. It must feel and behave like the eventual product while making network boundaries unmistakable.

## Product surfaces

### Automation pipeline

The production target is:

```text
RSS → detect → download → prepare audio → transcribe → locate section
    → extract → validate → JSON → Markdown → archive catalog
```

The current build performs the same orchestration through mock implementations. Every transition is durably written to the JSON state store.

### Local archive

The archive is a static client of generated data. It provides:

- Dashboard totals, latest episode, recent recommendations, and pipeline version.
- Episode archive with status, review state, listen link, and generated summary link.
- Searchable and filterable flattened picks.
- Pick details including targets, hold, reasoning, caveats, confidence, timestamp, and evidence.
- Processing-status overview.
- About view documenting trust rules and production boundaries.

## Functional requirements

1. Episode identity is based on RSS GUID, not mutable title or publication time.
2. A terminal episode is skipped on ordinary reruns.
3. Successful episodes publish `metadata.json`, `summary.json`, and `summary.md`.
4. Failed episodes publish metadata and failure details without pretending a summary exists.
5. `archive/index.json` is the frontend master catalog.
6. `archive/cards.json` contains every recommendation as a flattened record.
7. Markdown is reproducibly rendered from summary JSON.
8. Every recommendation has a deterministic unique ID.
9. Unknown values remain `null`.
10. Review and failure states remain visible in both data and UI.

## Fixture acceptance criteria

The included fixture bundle contains five clearly synthetic episodes and fifteen recommendations, including:

- Three completed episodes, one needs-review episode, and one failed episode.
- Repeated cards across episodes.
- Confirmed, likely, ambiguous, and unknown printings.
- Missing entry, hold, exit, and confidence values.
- Multiple hosts and a three-host episode.
- Ambiguous cross-talk and an intentional download failure.

## Non-goals for Revision 1

- Live RSS or historical backfill.
- Real MP3 download, conversion, or transcription.
- GitHub Actions or Pages.
- Email, Discord, price tracking, performance scoring, authentication, or database storage.
- ManaSpec integration.

## Success measures for the next production phase

- No duplicate published episode for the same RSS GUID.
- Card-name accuracy measured on a representative transcript set.
- No unsupported entry, exit, printing, host, or confidence value in evaluation output.
- Clear `needs_review` routing when section boundaries, speakers, prices, or printings are ambiguous.
- A failed scheduled run can retry without corrupting or duplicating published data.

