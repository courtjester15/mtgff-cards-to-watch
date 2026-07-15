"use strict";

const state = { index: null, cards: [], route: "dashboard", query: "", status: "all" };
const app = document.querySelector("#app");
const pageTitle = document.querySelector("#page-title");
const dialog = document.querySelector("#pick-dialog");
const dialogContent = document.querySelector("#dialog-content");

const routes = {
  dashboard: { title: "Dashboard", render: renderDashboard },
  episodes: { title: "Episode Archive", render: renderEpisodes },
  picks: { title: "All Picks", render: renderPicks },
  status: { title: "Processing Status", render: renderStatus },
  about: { title: "Settings / About", render: renderAbout },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(value) {
  try {
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
  } catch { return "#"; }
}

function formatDate(value, long = false) {
  if (!value) return "Unknown date";
  return new Intl.DateTimeFormat("en-US", long
    ? { month: "long", day: "numeric", year: "numeric" }
    : { month: "short", day: "numeric", year: "numeric" }
  ).format(new Date(value));
}

function display(value, fallback = "Not stated") {
  return value === null || value === undefined || value === "" ? fallback : escapeHtml(value);
}

function target(value) { return value ? escapeHtml(value.raw) : "Not stated"; }
function label(value) { return String(value ?? "unknown").replaceAll("_", " "); }
function badge(value, kind = "status") { return `<span class="${kind} ${escapeHtml(value ?? "unknown")}">${escapeHtml(label(value))}</span>`; }
function episodeSummaryUrl(episode) { return `../archive/${episode.directory}/summary.md`; }

async function loadData() {
  app.innerHTML = `<div class="loading"><span></span> Loading archive…</div>`;
  try {
    const nonce = Date.now();
    const [indexResponse, cardsResponse] = await Promise.all([
      fetch(`../archive/index.json?v=${nonce}`),
      fetch(`../archive/cards.json?v=${nonce}`),
    ]);
    if (!indexResponse.ok || !cardsResponse.ok) throw new Error("Generated archive files were not found.");
    state.index = await indexResponse.json();
    const cardsPayload = await cardsResponse.json();
    state.cards = cardsPayload.cards;
    document.querySelector("#side-version").textContent = `Pipeline ${state.index.metadata.pipeline_version}`;
    renderRoute();
  } catch (error) {
    app.innerHTML = `<div class="empty-state"><strong>Archive could not be loaded</strong><p>${escapeHtml(error.message)}</p><p>Run <code>python -m ffw run</code>, then use <code>python -m ffw serve</code>.</p></div>`;
  }
}

function setRoute() {
  const requested = window.location.hash.replace("#", "") || "dashboard";
  state.route = routes[requested] ? requested : "dashboard";
  renderRoute();
}

function renderRoute() {
  if (!state.index) return;
  const route = routes[state.route];
  pageTitle.textContent = route.title;
  document.querySelectorAll("nav a").forEach((link) => link.classList.toggle("active", link.dataset.route === state.route));
  app.innerHTML = route.render();
  bindPageEvents();
}

function renderDashboard() {
  const { counts, latest_episode: latest, recent_picks: recent } = state.index;
  return `
    <section class="grid metrics" aria-label="Archive totals">
      ${metric("Episodes", counts.episodes, "synthetic fixtures")}
      ${metric("Picks", counts.picks, "structured records")}
      ${metric("Completed", counts.completed, "validated outputs")}
      ${metric("Needs review", counts.needs_review, "human attention")}
      ${metric("Failed", counts.failed, "exercised failure")}
    </section>
    <section class="grid dashboard-grid">
      <article class="panel">
        <div class="panel-head"><h2>Latest episode</h2><a href="#episodes">View archive →</a></div>
        <div class="panel-body latest">
          <div>${badge(latest.processing_status)} ${latest.review_state === "needs_review" ? badge("needs_review") : ""}</div>
          <div><p class="eyebrow">Episode ${latest.episode_number} · ${formatDate(latest.published_at)}</p><h3>${escapeHtml(latest.title)}</h3></div>
          <div class="latest-meta"><span>${latest.pick_count} picks</span><span>${escapeHtml(latest.hosts.join(" · "))}</span><span>GUID ${escapeHtml(latest.guid)}</span></div>
          <div class="latest-actions"><a class="button" href="${safeUrl(latest.audio_url)}" target="_blank" rel="noreferrer">Listen</a><a class="button secondary" href="${episodeSummaryUrl(latest)}" target="_blank">Open summary</a></div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head"><h2>Recent recommendations</h2><a href="#picks">View all →</a></div>
        <div class="panel-body recommendation-list">
          ${recent.map((pick) => `<div class="recommendation-row" data-pick-id="${escapeHtml(pick.id)}" role="button" tabindex="0"><div><strong>${escapeHtml(pick.card)}</strong><p>${escapeHtml(pick.recommendation)}</p></div><time>${escapeHtml(pick.timestamp)}</time></div>`).join("")}
        </div>
      </article>
    </section>`;
}

function metric(name, value, note) {
  return `<article class="metric"><p>${escapeHtml(name)}</p><strong>${Number(value)}</strong><small>${escapeHtml(note)}</small></article>`;
}

function renderEpisodes() {
  return `
    <div class="toolbar"><label class="search"><input id="episode-search" type="search" placeholder="Search episode title, number, host…" value="${escapeHtml(state.query)}"></label><select id="episode-status" aria-label="Filter by status"><option value="all">All statuses</option>${["complete", "needs_review", "failed"].map((value) => `<option value="${value}" ${state.status === value ? "selected" : ""}>${label(value)}</option>`).join("")}</select></div>
    <div class="table-wrap"><table><thead><tr><th>Episode</th><th>Date</th><th>Title</th><th>Status</th><th>Picks</th><th>Review</th><th>Listen</th><th>Open</th></tr></thead><tbody id="episode-rows">${episodeRows()}</tbody></table></div>`;
}

function episodeRows() {
  const query = state.query.toLowerCase();
  const episodes = state.index.episodes.filter((episode) => {
    const haystack = `${episode.episode_number} ${episode.title} ${episode.hosts.join(" ")}`.toLowerCase();
    return haystack.includes(query) && (state.status === "all" || episode.processing_status === state.status);
  });
  if (!episodes.length) return `<tr><td colspan="8">No matching episodes.</td></tr>`;
  return episodes.map((episode) => `<tr><td><strong>#${episode.episode_number}</strong></td><td>${formatDate(episode.published_at)}</td><td><strong>${escapeHtml(episode.title)}</strong><br><span class="muted">${escapeHtml(episode.hosts.join(", "))}</span></td><td>${badge(episode.processing_status)}</td><td>${episode.pick_count}</td><td>${escapeHtml(label(episode.review_state))}</td><td><a class="link-button" href="${safeUrl(episode.audio_url)}" target="_blank" rel="noreferrer">Listen</a></td><td>${episode.outputs.summary_markdown ? `<a class="link-button" href="${episodeSummaryUrl(episode)}" target="_blank">Open</a>` : `<span class="muted">Unavailable</span>`}</td></tr>`).join("");
}

function renderPicks() {
  return `
    <div class="toolbar"><label class="search"><input id="pick-search" type="search" placeholder="Search card, printing, host, recommendation…" value="${escapeHtml(state.query)}"></label><select id="pick-status" aria-label="Filter by review status"><option value="all">All review states</option>${["approved", "pending", "needs_review"].map((value) => `<option value="${value}" ${state.status === value ? "selected" : ""}>${label(value)}</option>`).join("")}</select></div>
    <div class="table-wrap"><table><thead><tr><th>Card</th><th>Printing</th><th>Host</th><th>Entry</th><th>Hold</th><th>Exit</th><th>Confidence</th><th>Episode</th><th>Time</th><th>Status</th><th></th></tr></thead><tbody id="pick-rows">${pickRows()}</tbody></table></div>`;
}

function pickRows() {
  const query = state.query.toLowerCase();
  const picks = state.cards.filter((pick) => {
    const haystack = `${pick.card} ${pick.printing ?? ""} ${pick.hosts.join(" ")} ${pick.recommendation} ${pick.episode.title}`.toLowerCase();
    return haystack.includes(query) && (state.status === "all" || pick.review_status === state.status);
  });
  if (!picks.length) return `<tr><td colspan="11">No matching picks.</td></tr>`;
  return picks.map((pick) => `<tr><td><strong>${escapeHtml(pick.card)}</strong></td><td>${display(pick.printing)}<br>${pick.printing_certainty ? badge(pick.printing_certainty, "certainty") : ""}</td><td>${escapeHtml(pick.hosts.join(", "))}</td><td>${target(pick.entry_target)}</td><td>${display(pick.hold)}</td><td>${target(pick.exit_target)}</td><td>${pick.confidence ? badge(pick.confidence, "confidence") : `<span class="muted">Not stated</span>`}</td><td>#${pick.episode.episode_number}</td><td>${display(pick.timestamp)}</td><td>${badge(pick.review_status)}</td><td><button class="link-button" data-pick-id="${escapeHtml(pick.id)}">Details</button></td></tr>`).join("");
}

function renderStatus() {
  return `<article class="panel"><div class="panel-head"><h2>Fixture processing outcomes</h2><span class="muted">${state.index.episodes.length} episodes</span></div><div class="panel-body status-timeline">${state.index.episodes.map((episode) => `<div class="status-card"><span class="episode-no">${episode.episode_number}</span><div><strong>${escapeHtml(episode.title)}</strong><small>${episode.review_reason ? escapeHtml(episode.review_reason) : `${episode.pick_count} structured picks · ${formatDate(episode.published_at)}`}</small></div>${badge(episode.processing_status)}</div>`).join("")}</div></article>`;
}

function renderAbout() {
  return `<section class="grid about-grid">
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Project</p><h2>FFW is two products sharing one contract.</h2><p>The Python pipeline produces versioned JSON. This local vanilla JavaScript application visualizes it. Neither layer imports or executes the other.</p><p><strong>Pipeline:</strong> ${escapeHtml(state.index.metadata.pipeline_version)}<br><strong>Schema:</strong> ${escapeHtml(state.index.schema_version)}<br><strong>Source:</strong> ${escapeHtml(state.index.metadata.generated_from)}</p></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Trust rules</p><h2>Unknown means null.</h2><ul><li>No missing price, printing, host, or confidence is inferred.</li><li>Every recommendation requires evidence and a timestamp.</li><li>Markdown is rendered deterministically from JSON.</li><li>Ambiguity is surfaced as review state, not hidden.</li></ul></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Local commands</p><h2>Credential-free workflow</h2><p><code>python -m ffw run</code><br><code>python -m ffw validate</code><br><code>python -m ffw render</code><br><code>python -m ffw serve</code></p></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Current boundary</p><h2>Production integrations are scaffolded.</h2><p>Live RSS, MP3 download, audio conversion, OpenAI transcription, extraction, GitHub Actions, Pages, and notifications remain deliberately disabled until credentials and production policy are supplied.</p></div></article>
  </section>`;
}

function bindPageEvents() {
  bindPickButtons();
  const episodeSearch = document.querySelector("#episode-search");
  const episodeStatus = document.querySelector("#episode-status");
  if (episodeSearch) episodeSearch.addEventListener("input", () => { state.query = episodeSearch.value; document.querySelector("#episode-rows").innerHTML = episodeRows(); });
  if (episodeStatus) episodeStatus.addEventListener("change", () => { state.status = episodeStatus.value; document.querySelector("#episode-rows").innerHTML = episodeRows(); });
  const pickSearch = document.querySelector("#pick-search");
  const pickStatus = document.querySelector("#pick-status");
  if (pickSearch) pickSearch.addEventListener("input", () => { state.query = pickSearch.value; document.querySelector("#pick-rows").innerHTML = pickRows(); bindPickButtons(); });
  if (pickStatus) pickStatus.addEventListener("change", () => { state.status = pickStatus.value; document.querySelector("#pick-rows").innerHTML = pickRows(); bindPickButtons(); });
}

function bindPickButtons() {
  document.querySelectorAll("[data-pick-id]").forEach((element) => {
    const open = () => showPick(element.dataset.pickId);
    element.addEventListener("click", open);
    element.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) open(); });
  });
}

function showPick(id) {
  const pick = state.cards.find((item) => item.id === id);
  if (!pick) return;
  dialogContent.innerHTML = `<div class="dialog-content"><p class="eyebrow">Episode ${pick.episode.episode_number} · ${formatDate(pick.episode.published_at, true)}</p><h2 id="dialog-card">${escapeHtml(pick.card)}</h2><div class="dialog-sub">${display(pick.printing)} · ${pick.printing_certainty ? label(pick.printing_certainty) : "printing not stated"} · ${escapeHtml(pick.hosts.join(", "))}</div><div class="detail-grid"><div class="detail-box"><small>Entry</small><strong>${target(pick.entry_target)}</strong></div><div class="detail-box"><small>Hold</small><strong>${display(pick.hold)}</strong></div><div class="detail-box"><small>Exit</small><strong>${target(pick.exit_target)}</strong></div></div><div class="detail-section"><h3>Recommendation</h3><p>${escapeHtml(pick.recommendation)}</p></div><div class="detail-section"><h3>Reasoning</h3><ul>${pick.reasoning.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("") || "<li>Not stated</li>"}</ul></div><div class="detail-section"><h3>Caveats</h3><ul>${pick.caveats.map((caveat) => `<li>${escapeHtml(caveat)}</li>`).join("") || "<li>None stated</li>"}</ul></div><div class="detail-section"><h3>Evidence · ${display(pick.timestamp)}</h3><div class="evidence">${escapeHtml(pick.evidence_excerpt)}</div></div><div class="latest-actions" style="margin-top:20px"><a class="button" href="${safeUrl(pick.listen_url)}" target="_blank" rel="noreferrer">Listen at timestamp</a>${badge(pick.review_status)}</div></div>`;
  dialog.showModal();
}

document.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
document.querySelector("#refresh-button").addEventListener("click", loadData);
window.addEventListener("hashchange", () => { state.query = ""; state.status = "all"; setRoute(); });
state.route = window.location.hash.replace("#", "") || "dashboard";
loadData();
