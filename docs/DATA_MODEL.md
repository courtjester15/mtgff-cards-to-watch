# FFW Data Model

## Canonical records

`summary.json` is canonical for an episode's extracted recommendations. `summary.md`, `index.json`, and `cards.json` are derived views and can be regenerated.

The versioned contract is defined in [`schemas/cards-to-watch.schema.json`](../schemas/cards-to-watch.schema.json).

## Episode identity

| Field | Type | Rule |
|---|---|---|
| `guid` | string | Required stable identity from RSS. |
| `episode_number` | integer | Display and sorting aid; not identity. |
| `title` | string | Publisher-controlled and mutable. |
| `published_at` | date-time | Original release time. |
| `audio_url` | string | Enclosure or equivalent audio URL. |
| `episode_url` | string | Human-facing episode page. |
| `duration_seconds` | integer/null | Unknown remains null. |
| `hosts` | string[] | Explicitly identified hosts only. |

## Recommendation

| Field | Type | Notes |
|---|---|---|
| `id` | string | Deterministic `pick-` ID. |
| `card` | string | Required source card name. |
| `printing` | string/null | Exact printing only when supported. |
| `printing_certainty` | enum/null | `confirmed`, `likely`, `ambiguous`, or null. |
| `hosts` | string[] | Speakers responsible for the recommendation. |
| `recommendation` | string | Faithful action or stance; no added opinion. |
| `entry_target` | target/null | Preserves source phrase plus optional numeric bounds. |
| `hold` | string/null | Duration or condition exactly as expressed. |
| `exit_target` | target/null | Preserves source phrase plus optional numeric bounds. |
| `reasoning` | string[] | Host reasoning only. |
| `caveats` | string[] | Risks and qualifications stated in the source. |
| `confidence` | enum/null | Only explicit or unmistakable confidence. |
| `start_seconds` / `end_seconds` | integer/null | Evidence span. Production successful picks require a start. |
| `evidence_excerpt` | string | Short audit excerpt, not a full transcript. |
| `review_status` | enum | `approved`, `pending`, or `needs_review`. |
| `listen_url` | string | Audio URL with best-effort time fragment. |

### Target shape

```json
{
  "raw": "$13 to $15",
  "currency": "USD",
  "minimum": 13.0,
  "maximum": 15.0
}
```

`raw` is required whenever a target object exists. A target never exists merely because the transcript mentions the current market price.

## Stable pick identifier

The ID is the first 16 hexadecimal characters of SHA-256 over:

```text
normalized episode GUID | normalized card name | start seconds | normalized printing
```

This is better than `episodeGuid-cardIndex` because extraction ordering can change during regeneration. It distinguishes repeated mentions of one card by timestamp and printing while remaining stable when unrelated picks are added or reordered.

Changing a material identity input intentionally produces a new ID. Future manual reconciliation can preserve aliases if a corrected timestamp would otherwise break an external reference.

## Pipeline metadata

Every successful episode records:

- Pipeline version.
- Schema version.
- Transcription model.
- Extraction model.
- Prompt version.
- Processed timestamp.
- Complete processing-state history.
- Review state and reason.
- Structured failure when applicable.

## Processing states

Canonical serialized values are lowercase snake case:

```text
detected → downloading → downloaded → transcribing → transcribed
         → extracting → extracted → complete | needs_review
         ↘ failed from any stage
```

The state store is operational memory. Episode metadata is the immutable-style audit view captured with the output. `archive/index.json` is a frontend projection and must not be used to resume pipeline work.

## Catalogs

`archive/index.json` contains metadata, counts, status counts, newest episode, recent picks, and all episode summaries required by navigation.

`archive/cards.json` repeats episode identity inside each flattened recommendation. This slight denormalization makes native search simple and will support Fuse.js or future imports without loading every episode file.

