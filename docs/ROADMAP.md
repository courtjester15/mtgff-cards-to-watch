# ManaIntel Roadmap

This roadmap describes sequencing, not dates. Each phase should preserve a usable archive and avoid building analytics before enough trustworthy history exists.

## Phase 0 — FFW proof of concept

Status: current foundation.

- Validate the MTG Fast Finance RSS/audio/transcription/extraction pipeline.
- Preserve evidence, uncertainty, durable state, deterministic output, and a static searchable archive.
- Keep synthetic and live boundaries conspicuous.

Exit condition: representative live extraction can be evaluated and reviewed without duplicate or unsupported records.

## Phase 1 — ManaIntel core contract

- Introduce stable `source`, `source_item`, and source-agnostic `recommendation` records.
- Add `source_type` and a generic source reference that supports timestamps, paragraphs, sections, and URLs.
- Separate mentioned prices from entry and exit targets.
- Separate source-stated confidence, extraction confidence, and review status.
- Build an adapter that maps existing FFW episode output to the common contract.
- Update archive projections and the frontend to use neutral source-item language.
- Keep the v1 episode outputs readable during migration or provide a deterministic migration tool.

Exit condition: the current podcast is fully represented through the common contract and the frontend has no MTG Fast Finance-specific logic.

## Phase 2 — Prove source agnosticism

- Add one permitted source of a materially different type, preferably written content or captioned video.
- Implement source-specific acquisition and extraction behind the common adapter boundary.
- Add cross-source filters and provenance-focused evaluation fixtures.
- Document retention and evidence rules for each supported source.

Exit condition: two source types publish into the same archive with no frontend schema branch.

## Phase 3 — Operational MVP

- Add scheduling, retry policy, observability, and a review queue.
- Define source onboarding criteria and permissions checks.
- Publish a stable versioned export for read-only consumers.
- Add backup, recovery, and schema migration procedures if storage outgrows Git JSON.

Exit condition: trusted sources update unattended, uncertain records are reviewable, and failures are recoverable.

## Phase 4 — Historical projections

Only after sufficient reviewed history exists:

- Card recommendation timelines.
- Repeated and independent-source mentions.
- Mention frequency and source agreement/disagreement.
- Aggregated stated entry and exit targets with currency and printing safeguards.

These remain derived projections. Canonical source records must not be rewritten to fit an analytic result.

## Phase 5 — Optional integrations

- Provide ManaSpec with a versioned read-only feed or API.
- Let ManaSpec create watchlists or decision records from a ManaIntel recommendation while retaining provenance.
- Consider reliability analysis only after defining price data, comparison windows, reprints/printings, methodology, and clear limitations.

## Guardrails for every phase

- Prefer archive quality and provenance over feature count.
- Do not add price tracking merely to make ingestion appear more analytical.
- Do not let source-specific fields escape the adapter boundary.
- Do not onboard content that cannot be accessed or excerpted appropriately.
- Do not present extraction confidence as investment confidence.
