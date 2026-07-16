# FFW Production Runbook

## Automated service

GitHub Actions runs `.github/workflows/ffw.yml` daily at 10:17 UTC (06:17 EDT / 05:17 EST). It reads the official MTG Fast Finance feed:

`https://feeds.soundcloud.com/users/soundcloud:users:201003125/sounds.rss`

The production stages are feed discovery, durable queueing, streamed temporary download, ffmpeg normalization/splitting, OpenAI diarized transcription, Cards to Watch boundary detection, schema-constrained extraction, validation, bot commit, and Pages deployment.

One concurrency group serializes all writers. Complete and needs-review records skip automatically. Failed live records retry only when explicitly requested. A runner crash after an external API response but before the next durable Git commit can cause a repeated API call; file-backed Git state cannot guarantee exactly-once external billing.

## One-time GitHub setup

1. Open the repository, then **Settings -> Secrets and variables -> Actions -> New repository secret**. For the temporary Gemini validation provider, name it exactly `GEMINI_API_KEY` and paste a valid Google AI Studio API key. For the OpenAI provider, name it exactly `OPENAI_API_KEY` and paste a valid OpenAI API key.
2. Open **Settings → Actions → General → Workflow permissions**. Select **Read and write permissions**, then save.
3. Open **Settings → Pages → Build and deployment → Source**. Select **GitHub Actions**.
4. If GitHub pauses the first deployment, open **Actions → FFW automated archive → the waiting run → Review deployments**, approve `github-pages`, and continue.

Never put the API key in `.env.example`, state, archive output, workflow inputs, issue text, or logs.

## Initial three-episode backfill

Open **Actions → FFW automated archive → Run workflow** and choose:

- mode: `backfill`
- episode_limit: `3`
- retry_failed: enabled only when repeating a failed attempt
- force_guid: blank
- deploy: enabled

The job attempts all three sequentially, validates the production-only catalog, commits durable changes with `chore(ffw): publish automated episode updates`, and deploys the site. A partial episode failure remains visible in processing status and the run summary.

## Recovery

- Retry all failed feed entries: dispatch `normal`, set `retry_failed` to true, and optionally limit the newest feed entries.
- Force one episode: dispatch `normal` and provide its exact RSS GUID in `force_guid`.
- Validate locally: set `FFW_MODE=live`, then run `python -m ffw validate`.
- Rebuild production projections locally: set `FFW_MODE=live`, then run `python -m ffw render`.
- Inspect workflow health: open **Actions → FFW automated archive**. The step summary shows pipeline result and whether durable outputs changed.

## Retention and cost

Raw MP3s, normalized chunks, and full transcripts remain in `.ffw-work/`, which is ignored and disposable on GitHub-hosted runners. Published records retain only source metadata, timestamps, short evidence excerpts, model/version audit data, JSON, and Markdown.

The OpenAI API may return token usage for extraction, but transcription usage availability varies by response. The pipeline records provider/model/chunk/duration metadata when available and does not fabricate a cost estimate. Monitor actual spend in the OpenAI API usage dashboard.
