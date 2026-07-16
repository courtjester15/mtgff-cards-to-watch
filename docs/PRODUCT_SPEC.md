# ManaIntel Product Specification

## Purpose

ManaIntel aggregates recommendations from trusted MTG finance sources into a consistent searchable archive. The canonical user question is:

> Who recommended what, when, and why?

The current FFW application proves this workflow for the Cards to Watch section of one podcast. It is the first ingestion implementation, not the final product boundary.

## Product surfaces

### Source ingestion

Every source adapter implements the same conceptual flow:

```text
discover source item -> acquire permitted content -> locate relevant material
  -> extract recommendations -> validate evidence -> publish common records
```

Source-specific work ends at normalization. Podcast transcription, video captions, HTML parsing, and community import are adapter concerns and must not leak into the archive or frontend.

### Recommendation archive

The MVP archive provides:

- A chronological view of recent recommendations.
- Search by card, source, contributor, source-item title, and recommendation text.
- Filters for publication date, source, source type, and review status.
- Recommendation detail with mentioned prices, targets, reasoning, confidence, and evidence.
- A link or reference back to the exact location in the source when possible.
- Visible processing and review status; uncertain records are never silently presented as approved.

## MVP functional requirements

1. Each source, source item, and recommendation has a stable identity.
2. Reprocessing a source item does not create duplicate recommendations.
3. Every recommendation identifies its source item, publication date, card, and faithful recommendation summary.
4. Mentioned market prices remain distinct from suggested entry and exit targets.
5. Unknown values remain `null`; extraction must not invent missing context.
6. Every published recommendation has a timestamp or source reference and short supporting evidence where permitted.
7. Confidence and review status are stored as data and exposed in the UI.
8. Failed ingestion remains auditable without publishing a fabricated or empty successful result.
9. The frontend consumes only the common archive contract and contains no source-specific parsing or presentation logic.
10. Generated or extracted text is clearly attributable to its source and can be verified against the source reference.
11. The archive supports deterministic rebuilds of derived catalogs and views.
12. Export boundaries are versioned so future consumers such as ManaSpec do not import pipeline internals.

## MVP entities

```text
Source -> Source item -> Recommendation -> Archive projections
```

- A **source** is a publisher, show, channel, publication, or community feed.
- A **source item** is an episode, video, article, newsletter issue, post, or curated discussion summary.
- A **recommendation** is a source-attributed claim about a card, with supporting context and evidence.
- An **archive projection** is a rebuildable search or display representation of canonical records.

See [Data Model](DATA_MODEL.md) for the target contract and the mapping from the current episode schema.

## Trust and content requirements

- Preserve source wording for prices and targets alongside any parsed numeric values.
- Keep evidence excerpts compact and store only content that is permitted and necessary.
- Distinguish source confidence from extraction confidence and editorial review status.
- Do not infer financial advice, sentiment, targets, speakers, printings, or currencies without support.
- Treat all imported content and extracted output as untrusted input.
- Clearly identify synthetic fixtures so they cannot be mistaken for real recommendations.

## Explicit non-goals for the MVP

- Live card-price tracking or market data.
- Price prediction, automated picks, or AI investment analysis.
- Portfolio, position, or transaction management.
- Performance scoring or source leaderboards.
- Recommendation alerts or trading automation.
- Social features or user-generated investment advice.
- Direct ManaSpec workflow integration.
- Trend, agreement, disagreement, or reliability analytics.

## Current FFW acceptance criteria

Until the common contract is implemented, the proof of concept retains its existing acceptance criteria:

- RSS GUID is the stable episode identity.
- Terminal episodes are skipped on ordinary reruns.
- Successful episodes publish `metadata.json`, `summary.json`, and deterministic `summary.md`.
- Failed episodes publish metadata without a false summary.
- `archive/index.json` and `archive/cards.json` are rebuildable frontend projections.
- Every recommendation has a deterministic ID, timestamp, evidence excerpt, and review state.
- The synthetic fixture set exercises repeats, missing values, ambiguous speech, multiple hosts, and failure handling.

## MVP success measures

- Users can answer the five questions in the [Vision](VISION.md) from the archive without inspecting raw pipeline data.
- No duplicate source item or recommendation is published during normal reprocessing.
- Card names, source attribution, prices, and references meet thresholds defined on representative evaluation fixtures.
- Unsupported values are absent rather than inferred.
- Ambiguous records route to review with an actionable reason.
- A failed run can retry without corrupting or duplicating published data.
- A second source type can be added without changing frontend recommendation logic.
