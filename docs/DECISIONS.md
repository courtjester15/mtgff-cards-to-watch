# FFW Architecture Decisions

## ADR-001 — Python package is `ffw`

**Decision:** Use `ffw` and expose `python -m ffw`.

**Reason:** This matches the internal project identity and keeps the CLI concise. The longer repository name remains useful externally.

## ADR-002 — JSON is the integration boundary

**Decision:** The pipeline and frontend share versioned generated JSON and nothing else.

**Reason:** The archive can remain static, future Pages publication is simple, and ManaSpec can consume data without importing pipeline internals.

## ADR-003 — Standard library first

**Decision:** Revision 1 uses no downloaded runtime packages. The UI uses native JavaScript, `Intl`, tables, and `<dialog>`.

**Reason:** The workspace contained no approved local copies of Tabulator, Fuse.js, Day.js, Micromodal, or Tippy.js. Native implementations are sufficient for fifteen fixtures and preserve the no-download constraint.

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

## Known risks

- The manual validator implements project invariants but does not execute the full JSON Schema vocabulary because no JSON Schema package was downloaded.
- Semantic fabrication cannot be detected by structural validation alone; production needs evaluation fixtures and review thresholds.
- A single JSON state file assumes serialized writers.
- Timestamp URL fragments are not supported uniformly by podcast hosts.
- Native table rendering is intentionally simple and may need virtualization for a large historical archive.
- Corrected card names, printings, or timestamps can change deterministic IDs; future imports may require an alias map.

