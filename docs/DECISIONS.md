# ManaIntel and FFW Architecture Decisions

## ADR-001 — Python package is `ffw`

**Decision:** Use `ffw` and expose `python -m ffw`.

**Reason:** This matches the internal project identity and keeps the CLI concise. The longer repository name remains useful externally.

## ADR-002 — JSON is the integration boundary

**Decision:** The pipeline and frontend share versioned generated JSON and nothing else.

**Reason:** The archive can remain static, future Pages publication is simple, and ManaSpec can consume data without importing pipeline internals.

## ADR-003 — Standard library first

**Decision:** Revision 1 used no downloaded runtime packages. The UI continues to use native JavaScript, `Intl`, tables, and `<dialog>`. Version 0.2 adds the official OpenAI Python dependency for opt-in live adapters while mock mode remains credential-free.

**Reason:** The workspace contained no approved local copies of Tabulator, Fuse.js, Day.js, Micromodal, or Tippy.js. Native frontend implementations are sufficient for the current archive. The live model API is a separate integration need and does not justify unrelated UI dependencies.

**Future recommendation:** Evaluate Fuse.js when fuzzy search is needed and Tabulator when sorting, column controls, or thousands of rows justify the dependency. Keep library files vendored or pinned rather than CDN-dependent.

## ADR-004 — Stable pick IDs use content identity, not array index

**Decision:** Hash GUID, card, timestamp, and printing.

**Reason:** Array indexes change when extraction order changes. The selected identity remains stable during unrelated additions and supports repeated cards.

## ADR-005 — Failed episodes publish metadata only

**Decision:** A failed folder contains `metadata.json`; summary outputs are null and absent.

**Reason:** Empty or fabricated summaries would look successful. The catalog still needs the failure for status reporting.

## ADR-006 — Full transcripts are not durable archive output

**Decision:** Keep only short evidence excerpts and timestamps in the published contract.

**Reason:** This limits repository growth and copyright exposure while retaining an audit trail. Production debugging may use short-lived protected artifacts.

## ADR-007 — Git JSON state is sufficient for v1

**Decision:** Store episode state in one atomic JSON manifest keyed by GUID.

**Reason:** The expected cadence and concurrency are tiny. A database would add operational burden without improving the local experiment. GitHub Actions must later serialize runs with a concurrency group.

## ADR-008 — Review is data, not an exception

**Decision:** `needs_review` is a successful extraction outcome with complete outputs; infrastructure or stage errors are `failed`.

**Reason:** Ambiguity is expected in speech. Preserving uncertain results for review is different from pretending the pipeline could not run.

## ADR-009 — Current fixture corpus stays conspicuously synthetic

**Decision:** Every fixture title, evidence quote, catalog, summary, and screen carries a synthetic marker.

**Reason:** Test recommendations must never be confused with host statements or actionable financial advice.

## ADR-010 — ManaIntel is the product; FFW is the first adapter

**Decision:** Treat the existing `ffw` package and episode contract as the MTG Fast Finance proof of concept and first source adapter, not as the final product boundary.

**Reason:** The implemented pipeline is valuable and testable, but podcast-specific concepts cannot represent video, written, and community sources without leaking special cases throughout the system.

## ADR-011 — Normalize to source, source item, and recommendation

**Decision:** Future adapters publish a common hierarchy of `source -> source_item -> recommendation`. The frontend consumes only common archive projections.

**Reason:** Source acquisition varies substantially, while the user-facing questions and recommendation fields remain consistent. Normalization keeps source-specific complexity at the ingestion edge.

## ADR-012 — Provenance is required and source-type neutral

**Decision:** Every published recommendation requires a generic source reference and compact evidence where permitted. References support timestamps, sections, paragraphs, pages, messages, and deep links.

**Reason:** A timestamp-only contract excludes written and community sources. A generic locator preserves verification without inventing a media-specific field.

## ADR-013 — Separate price context, targets, and confidence types

**Decision:** Mentioned prices are modeled separately from entry and exit targets. Source-stated confidence, extraction confidence, and review status are also distinct.

**Reason:** Collapsing these concepts changes source meaning. A market price is not automatically an entry recommendation, and pipeline certainty is not investment conviction.

## ADR-014 — Analytics and ManaSpec integration are projections, not ingestion concerns

**Decision:** Defer trends, reliability, portfolio features, and ManaSpec workflows. Future analytics and integrations consume versioned canonical recommendations or rebuildable projections.

**Reason:** ManaIntel's first responsibility is a trustworthy archive. Keeping downstream analysis outside ingestion prevents speculative product features from distorting captured source data.

## ADR-015 — Migrate additively through an FFW normalizer

**Decision:** Introduce the common contract beside v1 and map existing FFW summaries into it before replacing v1 paths or adding multiple adapters.

**Reason:** An additive compatibility layer preserves the working proof of concept, makes migration testable, and proves the common model against real implementation constraints.

## ADR-016 — GitHub Actions is the Revision 2 production host

**Decision:** Run one serialized daily workflow at 10:17 UTC, commit durable JSON state and generated outputs with the Actions bot, and deploy a clean GitHub Pages artifact.

**Reason:** The podcast cadence and sequential workload fit hosted runners, repository JSON remains auditable, Pages serves the existing static contract, and Jason's laptop can remain off. Audio and transcripts are disposable runner data. A database or long-running host becomes appropriate only if runner limits, concurrency, archive scale, or review workflows outgrow this model.

## ADR-017 — OpenAI diarized transcription plus structured extraction

**Decision:** Split normalized mono audio below provider upload limits, transcribe with configurable `gpt-4o-transcribe-diarize`, detect Cards to Watch boundaries separately, and extract with configurable schema-constrained Responses API output. The initial extraction default is `gpt-5.6-luna` for cost-sensitive structured work.

**Reason:** Diarized segments provide the timestamps and speaker hints required for evidence, while a separate structured pass prevents whole-episode summarization and enforces null handling. Model names remain environment-configurable as availability and cost change.

## Known risks

- The manual validator implements project invariants but does not execute the full JSON Schema vocabulary because no JSON Schema package was downloaded.
- Semantic fabrication cannot be detected by structural validation alone; production needs evaluation fixtures and review thresholds.
- A single JSON state file assumes serialized writers.
- Timestamp URL fragments are not supported uniformly by podcast hosts.
- Native table rendering is intentionally simple and may need virtualization for a large historical archive.
- Corrected card names, printings, or timestamps can change deterministic IDs; future imports may require an alias map.
