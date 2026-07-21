# ManaIntel Product Vision

> **Maintenance-mode scope (2026-07-17):** The supported product is now the single-source MTG Fast Finance Cards to Watch utility. The broader multi-source vision below is retained as historical product thinking, not an active roadmap. After a bounded final functional pass, portfolio attention moves to ManaSpec adoption and GalleyFlow.

## Product definition

ManaIntel was conceived as a lightweight Magic: The Gathering finance intelligence platform aggregating recommendations from trusted sources into one consistent, searchable archive. Its shipped maintenance-mode form focuses on one trusted podcast source.

Its primary job is to answer:

> Who recommended what, when, and why?

ManaIntel is an information aggregator. It is not a price tracker, portfolio manager, recommendation engine, or AI analyst. It preserves and organizes source claims; the user decides what matters.

## Product promise

A user should be able to quickly answer:

- What cards were recommended this week?
- Which source recommended this card?
- When was it first mentioned?
- What entry or target price was suggested?
- What exactly was said, and where can I verify it?

If these questions are easy to answer, ManaIntel has accomplished its mission.

## MVP

For every recommendation, capture and display:

- Source and contributor.
- Source item: episode, video, article, newsletter, or discussion.
- Publication date.
- Card name and printing when explicitly identified.
- Faithful recommendation summary.
- Mentioned prices.
- Suggested entry and exit targets when available.
- Timestamp, section, paragraph, or other source reference.
- Short supporting evidence where permitted.
- Confidence and review status.

The MVP is a clean searchable archive over those records. It does not require analytics, live prices, accounts, portfolios, alerts, or automated investment judgments.

## Source scope

The architecture should support adapters for:

- Podcasts, beginning with MTG Fast Finance and potentially other finance shows.
- Videos from trusted MTG finance creators.
- Articles, blogs, and newsletters where access and reuse are permitted.
- Public community discussions and curated summaries.

Adding a source must not require source-specific behavior in the archive UI. Each adapter discovers a source item, obtains permitted content, extracts recommendations, attaches evidence, and publishes the common contract.

Source support is not the same as permission to ingest. Paywalled, private, licensed, or community content must be handled according to its access terms and should store only the minimum evidence needed for verification.

## Deferred analytics

Analytics become useful only after the archive has meaningful history. Possible later capabilities include:

- Repeated mentions and first/most-recent mention dates.
- Independent-source agreement or disagreement.
- Recommendation history for a card.
- Average stated entry and exit targets.
- Mention frequency.
- Carefully defined source reliability measures.

These are projections over the archive, not part of ingestion and not MVP requirements. Reliability in particular requires an explicit methodology and appropriate price data; it must never be presented as an opaque AI score.

## Relationship with ManaSpec

ManaIntel gathers and exposes structured source information. ManaSpec may later consume that information for watchlists, positions, and speculation workflows.

```text
ManaIntel recommendations -> versioned export/API -> ManaSpec decision workflow
```

ManaSpec should not duplicate ManaIntel's collection pipeline, and ManaIntel should not absorb ManaSpec's portfolio or decision-making responsibilities.

## Current proof of concept

The existing `ffw` package is the first source adapter and pipeline proof of concept. It is intentionally specialized for the Cards to Watch segment of MTG Fast Finance. Its episode schema, RSS identity, audio stages, generated Markdown, and static archive remain valid implementation assets, but they are not the final cross-source product contract.

The transition to ManaIntel should be incremental: keep the working pipeline, introduce the common source-item model beside it, then adapt FFW output into that model before adding a second source.
