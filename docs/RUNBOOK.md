# FFW Production Runbook

## Automated service

GitHub Actions runs `.github/workflows/ffw.yml` daily at 10:17 UTC (06:17 EDT / 05:17 EST). It reads the official MTG Fast Finance feed:

`https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss`

The production stages are feed discovery, durable queueing, streamed temporary download, ffmpeg normalization/splitting, OpenAI diarized transcription, Cards to Watch boundary detection, schema-constrained extraction, validation, bot commit, and Pages deployment.

One concurrency group serializes all writers. The daily `next` mode scans newest to oldest and processes at most one eligible episode. `complete` and `needs_review` records skip before download or provider calls, while failed records are skipped until a failed-only retry is explicitly requested. New releases therefore take priority and historical backfill resumes automatically afterward. A runner crash after an external API response but before the next durable Git commit can cause a repeated API call; file-backed Git state cannot guarantee exactly-once external billing.

## One-time GitHub setup

1. Open the repository, then **Settings -> Secrets and variables -> Actions -> New repository secret**. For the temporary Gemini validation provider, name it exactly `GEMINI_API_KEY` and paste a valid Google AI Studio API key. For the OpenAI provider, name it exactly `OPENAI_API_KEY` and paste a valid OpenAI API key.
2. Open **Settings → Actions → General → Workflow permissions**. Select **Read and write permissions**, then save.
3. Open **Settings → Pages → Build and deployment → Source**. Select **GitHub Actions**.
4. If GitHub pauses the first deployment, open **Actions → FFW automated archive → the waiting run → Review deployments**, approve `github-pages`, and continue.

## Controlled live validation

Manual live runs are intentionally capped. For the first historical episode, use `backfill`, `batch_size=1`, leave `force_guid` blank, and set `deploy=true`. The workflow rejects zero, blank, negative, and over-cap batch sizes so a manual run cannot accidentally process the full RSS feed. The limit counts eligible episodes after durable-state filtering, not the newest feed positions.

The first Gemini validation attempt used `gemini-2.5-flash`, which returned `404 NOT_FOUND` for this key because that model was not available to new users. That run also demonstrated why provider-wide failures must stop the batch: the old `episode_limit=0` default meant "all episodes" and published roughly 500 failed live records. The archive/state cleanup commit removes those generated failure records and keeps the synthetic fixture archive only.

Provider-wide failures include missing or invalid keys, unavailable models, quota exhaustion, and provider schema capability errors. Those failures should stop after the first attempted episode and fail the GitHub Action before commit/deploy. Episode-specific failures, such as an oversized audio file inside a limited run, can remain isolated to that episode.

Never put the API key in `.env.example`, state, archive output, workflow inputs, issue text, or logs.

## Controlled historical backfill

Open **Actions → FFW automated archive → Run workflow** and choose:

- mode: `backfill`
- batch_size: `3`
- force_guid: blank
- deploy: enabled

The job attempts all three sequentially, validates the production-only catalog, commits durable changes with `chore(ffw): publish automated episode updates`, and deploys the site. A partial episode failure remains visible in processing status and the run summary.

## Recovery

- Process one next eligible episode: dispatch `next` with `batch_size=1`.
- Process a controlled eligible batch: dispatch `backfill` with `batch_size` from 1 through 20.
- Retry failed episodes only: dispatch `retry_failed` and choose a `batch_size` from 1 through 20.
- Force one episode: choose any processing mode and provide its exact RSS GUID in `force_guid`; the override searches the full fetched feed and bypasses batch position limits.
- Validate locally: set `FFW_MODE=live`, then run `python -m ffw validate`.
- Rebuild production projections locally: set `FFW_MODE=live`, then run `python -m ffw render`.
- Inspect workflow health: open **Actions → FFW automated archive**. The publish summary reports selector counts, attempts, outcomes, and whether durable outputs changed. Deployment outcome is reported separately by the deployment job.

## Retention and cost

Raw MP3s, normalized chunks, and full transcripts remain in `.ffw-work/`, which is ignored and disposable on GitHub-hosted runners. Published records retain only source metadata, timestamps, short evidence excerpts, model/version audit data, JSON, and Markdown.

The OpenAI API may return token usage for extraction, but transcription usage availability varies by response. The pipeline records provider/model/chunk/duration metadata when available and does not fabricate a cost estimate. Monitor actual spend in the OpenAI API usage dashboard.
