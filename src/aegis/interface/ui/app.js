"use strict";

/* AEGIS dashboard application.
   Routing: hash-based (#/overview, #/experiments, #/runs, #/catalog,
   #/analysis, #/audit, #/system, #/experiment/:id, #/run/:id). */

const S = {
  token: null,
  auth: "pending", // pending | ok | bad
  experiments: [],
  runs: [],
  catalog: { targets: [], datasets: [] },
  hide: null, // last hide (bool) when dev login unavailable
  poll: null, // run-detail poller
  metricNames: new Set(),
};

const API = "";

const RUN_STATUSES = ["queued", "running", "retrying", "partial", "succeeded", "failed", "cancelled"];
const VERDICTS = ["pass", "warn", "block"];
const SEVERITIES = ["info", "low", "medium", "high", "critical"];
const DEFAULT_EVALUATOR = "aegis/deterministic/exact_match";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* ---------------------------------------------------------------- helpers */

function esc(v) {
  if (v == null) return "";
  return String(v).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function time(v) {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return esc(v);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

function rel(v) {
  if (!v) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "";
  const s = Math.round((d.getTime() - Date.now()) / 1000);
  const abs = Math.abs(s);
  const span = (n, u) => `${n}${u}${s < 0 ? " ago" : ""}`;
  if (abs < 60) return span(abs, "s");
  if (abs < 3600) return span(Math.round(abs / 60), "m");
  if (abs < 86400) return span(Math.round(abs / 3600), "h");
  return span(Math.round(abs / 86400), "d");
}

function badge(kind, label) {
  return `<span class="badge badge--${esc(kind)}">${esc(label != null ? label : kind)}</span>`;
}

function short(id, len = 12) {
  return id && id.length > len ? `${id.slice(0, len)}…` : (id || "");
}

function fmtScore(v) {
  if (v == null) return "—";
  const n = Number(v);
  return Number.isFinite(n) ? (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(3)) : esc(v);
}

function jsonify(v) {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
}

function parseError(err) {
  if (err && err.detail) return { status: err.status, detail: err.detail };
  return { status: 0, detail: "unknown error" };
}

/* ---------------------------------------------------------------- api */

async function api(path, opts = {}) {
  const headers = { Accept: "application/json" };
  if (S.token) headers.Authorization = "Bearer " + S.token;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.json);
    delete opts.json;
  }
  let res;
  try {
    res = await fetch(API + path, { ...opts, headers });
  } catch {
    const e = new Error("network error; is the API reachable?");
    e.status = 0;
    throw e;
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch { /* body not json */ }
    const e = new Error(detail);
    e.status = res.status;
    e.detail = detail;
    throw e;
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}

/* ---------------------------------------------------------------- toast/modal */

function toast(title, detail = "", kind = "success") {
  const box = $("#toasts");
  const el = document.createElement("div");
  el.className = `toast toast--${kind}`;
  el.setAttribute("role", "status");
  el.innerHTML = `<span class="toast-title">${esc(title)}</span>${detail ? `<span class="toast-detail">${esc(detail)}</span>` : ""}`;
  box.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 4200);
}

function openModal({ title, body, actions }) {
  const root = $("#modal-root");
  root.innerHTML = `
    <div class="modal-backdrop" data-action="modal-close"></div>
    <div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <div class="modal-head">
        <h2>${esc(title)}</h2>
        <button class="icon-btn" data-action="modal-close" aria-label="Close">×</button>
      </div>
      <div class="modal-body">${body}</div>
      <div class="modal-foot">${actions || ""}</div>
    </div>`;
  root.hidden = false;
  const first = root.querySelector("input, select, textarea, button:not(.icon-btn)");
  if (first) first.focus();
}

function closeModal() {
  const root = $("#modal-root");
  root.hidden = true;
  root.innerHTML = "";
}

function confirmDialog({ title, message, confirmLabel = "Confirm", kind = "danger", onConfirm, data }) {
  openModal({
    title,
    body: `<p class="mb-0">${esc(message)}</p>`,
    actions: `
      <button class="btn btn--subtle" data-action="modal-close">Cancel</button>
      <button class="btn btn--${kind}" data-action="confirm" data-data="${esc(JSON.stringify(data || {}))}">${esc(confirmLabel)}</button>`,
  });
  rootConfirm = onConfirm;
}

let rootConfirm = null;

/* ---------------------------------------------------------------- shell */

function setAuth(status, label) {
  S.auth = status;
  const el = $("#auth-state");
  el.className = "auth-state " + status;
  el.textContent = label;
}

function showNav(show) {
  $$("[data-nav]").forEach((b) => {
    b.disabled = !show;
    b.setAttribute("aria-disabled", show ? "false" : "true");
  });
  $("#quick-new").disabled = !show;
}

function push(route) {
  location.hash = "#/" + route;
}

function navigate() {
  if (S.poll) { clearInterval(S.poll); S.poll = null; }
  const raw = (location.hash || "#/overview").replace(/^#\//, "");
  const [seg, param] = raw.split("/");
  $$(".nav-tab").forEach((t) =>
    t.setAttribute("aria-current", t.dataset.route === seg ? "page" : "false"));
  const main = $("#main");
  window.scrollTo({ top: 0 });
  main.innerHTML = `<div class="loading"><span class="spinner"></span> Loading ${esc(seg)}…</div>`;

  const route = {
    overview: renderOverview,
    experiments: renderExperiments,
    experiment: () => renderExperiment(param),
    runs: renderRuns,
    run: () => renderRun(param),
    catalog: renderCatalog,
    analysis: renderAnalysis,
    audit: renderAudit,
    system: renderSystem,
  }[seg] || renderOverview;

  route()
    .then((html) => { main.innerHTML = html; })
    .catch((err) => {
      const { status, detail } = parseError(err);
      if (status === 401 || status === 403) {
        main.innerHTML = renderLogin(detail, status);
        return;
      }
      main.innerHTML = `
        <div class="error-banner">
          <span class="error-title">Request failed</span>
          <div><code>HTTP ${esc(String(status || "network"))}</code><br>${esc(detail)}</div>
        </div>`;
    });
}

/* ---------------------------------------------------------------- boot */

async function boot() {
  window.addEventListener("hashchange", navigate);
  document.addEventListener("click", onAction);
  document.addEventListener("keydown", onKey);
  try {
    S.token = (await api("/security/dev-token")).token;
  } catch (err) {
    const { status } = parseError(err);
    S.auth = "bad";
    S.hide = status === 403 || status === 404;
  }
  if (S.token) {
    setAuth("ok", "authenticated · dev token");
    showNav(true);
    await refreshAll();
  } else {
    setAuth("bad", "dev login unavailable ");
    showNav(false);
  }
  navigate();
}

async function refreshAll() {
  const [experiments, runs, catalog] = await Promise.all([
    api("/experiments").catch(() => []),
    api("/runs").catch(() => []),
    api("/catalog").catch(() => ({ targets: [], datasets: [] })),
  ]);
  S.experiments = experiments;
  S.runs = runs;
  S.catalog = catalog;
}

/* ---------------------------------------------------------------- components */

function pageHead(title, sub, actions = "") {
  return `
    <header class="page-head">
      <div>
        <h1 class="page-title">${esc(title)}</h1>
        ${sub ? `<p class="page-sub">${sub}</p>` : ""}
      </div>
      ${actions ? `<div class="page-actions">${actions}</div>` : ""}
    </header>`;
}

function empty(title, sub = "", action = "") {
  return `
    <div class="empty">
      <div class="empty-title">${esc(title)}</div>
      ${sub ? `<div class="empty-sub">${esc(sub)}</div>` : ""}
      ${action}
    </div>`;
}

function errorBox(err) {
  const { status, detail } = parseError(err);
  return `
    <div class="error-banner">
      <span class="error-title">HTTP ${esc(String(status || "network"))}</span>
      <div><code>${esc(detail)}</code></div>
    </div>`;
}

function tableBase(headers, rows, emptyHtml) {
  if (!rows.length) return emptyHtml;
  return `
    <div class="table-wrap"><table class="data">
      <thead><tr>${headers}</tr></thead>
      <tbody>${rows.join("")}</tbody>
    </table></div>`;
}

/* ---------------------------------------------------------------- overview */

async function renderOverview() {
  const [health] = await Promise.all([api("/health/live").catch(() => null)]);
  const runs = S.runs;
  const experiments = S.experiments;
  const active = runs.filter((r) => !["succeeded", "failed", "cancelled"].includes(r.status));
  const last = runs[0];

  const stat = (label, value, hint = "", cls = "") => `
    <div class="stat"><div class="stat-label">${label}</div>
      <div class="stat-value ${cls}">${value}</div>
      ${hint ? `<div class="stat-hint">${hint}</div>` : ""}</div>`;

  const healthBadge = health
    ? badge(health.overall === "healthy" ? "healthy" : "unhealthy", health.overall)
    : badge("error", "unavailable");

  const quickActions = `
    <button class="btn btn--primary" data-action="new-experiment">New experiment</button>
    <button class="btn btn--ghost" data-action="register-target">Register target</button>
    <button class="btn btn--ghost" data-action="register-dataset">Register dataset</button>`;

  const recentRuns = tableBase(
    `<th>Run</th><th>Experiment</th><th>Status</th><th>Metric</th><th>Created</th>`,
    runs.slice(0, 5).map((r) => {
      const exp = experiments.find((e) => e.id === r.experiment_id);
      return `
        <tr class="row-link" data-action="open-run" data-id="${esc(r.run_id)}">
          <td class="cell-main mono">${esc(short(r.run_id))}</td>
          <td>${exp ? esc(exp.name) : esc(short(r.experiment_id))}</td>
          <td>${badge(r.status)}</td>
          <td class="cell-second">${r.evidence_summary ? esc(Object.keys(r.evidence_summary).join(", ")) : "—"}</td>
          <td class="cell-second">${time(r.created_at)}</td>
        </tr>`;
    }),
    empty("No runs yet", "Submit a run from an experiment to see results here.",
      `<button class="btn btn--primary btn--sm" data-action="new-experiment">New experiment</button>`));

  const recentExperiments = tableBase(
    `<th>Experiment</th><th>Project</th><th>Status</th><th>Created</th><th>Runs</th>`,
    experiments.slice(0, 5).map((e) => `      
      <tr class="row-link" data-action="open-experiment" data-id="${esc(e.id)}">
        <td class="cell-main">${esc(e.name)}<br><span class="cell-second mono">${esc(short(e.id))}</span></td>
        <td class="cell-second mono">${esc(e.project_id)}</td>
        <td>${badge(e.status)}</td>
        <td class="cell-second">${time(e.created_at)}</td>
        <td class="cell-second">${e.run_count ?? "—"}</td>
      </tr>`,
    ),
    empty("No experiments yet", "Create an experiment from registered catalog versions.",
      `<button class="btn btn--primary btn--sm" data-action="new-experiment">New experiment</button>`));

  return `
    ${pageHead("Overview", "System pulse, recent runs and experiments.", "")}
    <div class="stat-grid">
      ${stat("Experiments", experiments.length, `${experiments.filter((e) => e.status === "running").length} running`)}
      ${stat("Runs", runs.length, `${active.length} in flight`)}
      ${stat("Last run", last ? badge(last.status) : "—", last ? time(last.finished_at || last.created_at) : "no runs yet")}
      ${stat("API health", healthBadge, health ? health.checks.map((c) => c.name).join(" · ") : "unauthenticated when offline")}
    </div>
    <div class="detail-grid">
      <section class="card card-flush" aria-label="Recent runs">
        <div class="card-head"><h2>Recent runs</h2>
          <span class="flex"><span class="auth-state ok"></span><button class="btn btn--sm btn--ghost" data-action="refresh">Refresh</button></span></div>
        <div class="card-body">${recentRuns}</div>
      </section>
      <section class="card card-flush" aria-label="Recent experiments">
        <div class="card-head"><h2>Experiments</h2>${quickActions}</div>
        <div class="card-body">${recentExperiments}</div>
      </section>
    </div>`;
}

/* ---------------------------------------------------------------- experiments */

async function renderExperiments() {
  const q = $("#exp-search") ? $("#exp-search").value.toLowerCase() : "";
  const filter = $("#exp-filter") ? $("#exp-filter").value : "";

  let list = S.experiments;
  if (q) list = list.filter((e) => (e.name || "").toLowerCase().includes(q) || (e.id || "").toLowerCase().includes(q));
  if (filter) list = list.filter((e) => e.status === filter);

  const rows = list.map((e) => `
    <tr class="row-link" data-action="open-experiment" data-id="${esc(e.id)}">
      <td class="cell-main">${esc(e.name)}<br><span class="cell-second mono">${esc(short(e.id, 16))}</span></td>
      <td class="cell-second mono">${esc(e.project_id)}</td>
      <td>${badge(e.status)}</td>
      <td class="cell-second">${time(e.created_at)}</td>
      <td class="cell-second">${e.clone_of ? `clone of <span class="mono">${esc(short(e.clone_of))}</span>` : "—"}</td>
    </tr>`);

  return `
    ${pageHead("Experiments", "Reproducible evaluation snapshots over registered catalog versions.",
      `<button class="btn btn--primary" data-action="new-experiment">New experiment</button>
       <button class="btn btn--ghost" data-action="refresh">Refresh</button>`)}
    <section class="card card-flush">
      <div class="toolbar" style="padding:10px 14px">
        <input class="input grow" id="exp-search" data-action="filter" placeholder="Search by name or id…" aria-label="Search experiments" />
        <select class="select" id="exp-filter" data-action="filter" aria-label="Filter by status">
          <option value="">All statuses</option>
          ${["created", "running", "succeeded", "failed", "cancelled"].map((s) => `<option value="${s}">${s}</option>`).join("")}
        </select>
      </div>
      ${tableBase(
        `<th>Name / id</th><th>Project</th><th>Status</th><th>Created</th><th>Lineage</th>`,
        rows,
        empty("No experiments" + (q ? " match your search" : " yet"), "Create one from registered targets and datasets in the catalog.", `<button class="btn btn--primary btn--sm" data-action="new-experiment">New experiment</button>`))}
    </section>`;
}

/* ---------------------------------------------------------------- experiment detail */

async function renderExperiment(id) {
  const exp = S.experiments.find((e) => e.id === id) || await api(`/experiments/${encodeURIComponent(id)}`);
  const runs = await api(`/experiments/${encodeURIComponent(id)}/runs`).catch(() => []);

  const verdicts = {};
  await Promise.all(runs.map((r) =>
    api(`/policy/verdict/${encodeURIComponent(r.run_id)}`)
      .then((v) => { verdicts[r.run_id] = v; })
      .catch(() => {})));

  const runRows = runs.map((r) => {
    const verdict = verdicts[r.run_id];
    return `
      <tr class="${["queued", "running", "retrying"].includes(r.status) ? "" : "row-link"}" data-action="open-run" data-id="${esc(r.run_id)}">
        <td class="cell-main mono">${esc(short(r.run_id, 16))}<br><span class="cell-second">${esc(short(r.experiment_id))}</span></td>
        <td>${badge(r.status)}</td>
        <td>${verdict ? badge(verdict.verdict, verdict.overridden ? verdict.verdict + " (overridden)" : verdict.verdict) : "—"}</td>
        <td class="cell-second">${time(r.created_at)}</td>
        <td class="cell-second">${r.finished_at ? time(r.finished_at) : (r.started_at ? `${rel(r.started_at)} running` : "queued")}</td>
        <td>${["queued", "running", "retrying", "partial"].includes(r.status) ? `<button class="btn btn--sm btn--danger" data-action="cancel-run" data-id="${esc(r.run_id)}">Cancel</button>` : ""}</td>
      </tr>`;
  });

  const snapshot = exp.snapshot || {};
  const snapshotPanel = snapshot.target_version_id ? `
    <section class="card">
      <div class="card-head"><h2>Snapshot (immutable)</h2></div>
      <div class="card-body">
        <dl class="kv">
          <dt>Target version</dt><dd class="mono">${esc(snapshot.target_version_id || "—")}</dd>
          <dt>Dataset version</dt><dd class="mono">${esc(snapshot.dataset_version_id || "—")}</dd>
          <dt>Evaluators</dt><dd class="mono">${(snapshot.evaluator_version_ids || []).map(esc).join("<br>") || "—"}</dd>
          <dt>Policy version</dt><dd class="mono">${esc(snapshot.policy_version_id || "none")}</dd>
          ${Object.keys(snapshot.settings || {}).length ? `<dt>Settings</dt><dd><pre class="code">${esc(jsonify(snapshot.settings))}</pre></dd>` : ""}
        </dl>
      </div>
    </section>` : "";

  return `
    ${pageHead(`Experiment: ${esc(exp.name)}`,
      `<span class="mono">${esc(exp.id)}</span> · project <span class="mono">${esc(exp.project_id)}</span> · ${badge(exp.status)}`)}
    <div class="flex flex-wrap">
      <button class="btn btn--primary" data-action="submit-run" data-id="${esc(exp.id)}">Submit run</button>
      ${exp.status !== "running" && exp.status !== "succeeded" ? `<button class="btn btn--ghost" data-action="start-experiment" data-id="${esc(exp.id)}">Start</button>` : ""}
      <button class="btn btn--ghost" data-action="clone-experiment" data-id="${esc(exp.id)}">Clone</button>
      <button class="btn btn--subtle" data-action="nav" data-route="experiments">Back</button>
    </div>
    ${snapshotPanel}
    <section class="card card-flush" aria-label="Runs for experiment">
      <div class="card-head"><h2>Runs</h2><span class="cell-second">${runs.length} total</span></div>
      <div class="card-body">
        ${tableBase(
          `<th>Run</th><th>Status</th><th>Gate</th><th>Created</th><th>Finished</th><th></th>`,
          runRows,
          empty("No runs for this experiment yet.", "Submit a run to enqueue it; an engine worker executes it.", `<button class="btn btn--primary btn--sm" data-action="submit-run" data-id="${esc(exp.id)}">Submit run</button>`))}
      </div>
    </section>`;
}

/* ---------------------------------------------------------------- runs */

async function renderRuns() {
  const q = $("#runs-search") ? $("#runs-search").value.toLowerCase() : "";
  const st = $("#runs-status") ? $("#runs-status").value : "";

  let list = S.runs;
  if (q) list = list.filter((r) => (r.run_id || "").toLowerCase().includes(q)
    || (S.experiments.find((e) => e.id === r.experiment_id) || {}).name?.toLowerCase().includes(q));
  if (st) list = list.filter((r) => r.status === st);

  const rows = list.map((r) => {
    const exp = S.experiments.find((e) => e.id === r.experiment_id);
    return `
      <tr class="row-link" data-action="open-run" data-id="${esc(r.run_id)}">
        <td class="cell-main mono">${esc(short(r.run_id, 16))}</td>
        <td>${exp ? esc(exp.name) : "—"}</td>
        <td>${badge(r.status)}</td>
        <td class="cell-second">${r.cancelled_by ? `by ${esc(r.cancelled_by)}` : (r.evidence_summary ? esc(Object.keys(r.evidence_summary).join(", ")) : "—")}</td>
        <td class="cell-second">${time(r.created_at)}</td>
        <td class="cell-second">${r.finished_at ? time(r.finished_at) : (r.started_at ? rel(r.started_at) : "—")}</td>
      </tr>`;
  });

  return `
    ${pageHead("Runs", "All runs in the tenant, newest first.",
      `<button class="btn btn--ghost" data-action="refresh">Refresh</button>`)}
    <section class="card card-flush">
      <div class="toolbar" style="padding:10px 14px">
        <input class="input grow" id="runs-search" data-action="filter" placeholder="Search run id or experiment…" aria-label="Search runs" />
        <select class="select" id="runs-status" data-action="filter" aria-label="Filter by status">
          <option value="">All statuses</option>
          ${RUN_STATUSES.map((s) => `<option value="${s}">${s}</option>`).join("")}
        </select>
      </div>
      ${tableBase(
        `<th>Run</th><th>Experiment</th><th>Status</th><th>Summary</th><th>Created</th><th>Started/finished</th>`,
        rows,
        empty("No runs yet.", "Runs appear here once an experiment is submitted.", `<button class="btn btn--primary btn--sm" data-action="new-experiment">New experiment</button>`))}
    </section>`;
}

/* ---------------------------------------------------------------- run detail */

async function renderRun(runId) {
  const [run, results, evidence, cost, traces, verdict] = await Promise.all([
    api(`/runs/${encodeURIComponent(runId)}`),
    api(`/runs/${encodeURIComponent(runId)}/results`).catch(() => []),
    api(`/evidence/runs/${encodeURIComponent(runId)}`).catch(() => []),
    api(`/observability/cost/${encodeURIComponent(runId)}`).catch(() => null),
    api(`/observability/traces/${encodeURIComponent(runId)}`).catch(() => []),
    api(`/policy/verdict/${encodeURIComponent(runId)}`).catch(() => null),
  ]);

  results.forEach((r) => S.metricNames.add(r.metric_name));

  const exp = S.experiments.find((e) => e.id === run.experiment_id) || {};

  const meta = `
    <section class="card">
      <div class="card-head"><h2>Run</h2>${badge(run.status)}</div>
      <div class="card-body">
        <dl class="kv">
          <dt>Run id</dt><dd class="mono">${esc(run.run_id)}</dd>
          <dt>Experiment</dt><dd>${esc((exp && exp.name) || run.experiment_id)}</dd>
          <dt>Created</dt><dd>${time(run.created_at)}</dd>
          <dt>Started</dt><dd>${time(run.started_at)}</dd>
          <dt>Finished</dt><dd>${time(run.finished_at)}</dd>
          <dt>Cancelled</dt><dd>${run.cancelled_by ? `${esc(run.cancelled_by)} @ ${time(run.cancelled_at)}` : "—"}</dd>
          <dt>Evidence summary</dt><dd class="mono">${esc(jsonify(run.evidence_summary || {}))}</dd>
        </dl>
        ${run.error ? `<pre class="code mt-2">${esc(jsonify(run.error))}</pre>` : ""}
      </div>
    </section>`;

  const costPanel = cost ? `
    <section class="card">
      <div class="card-head"><h2>Cost</h2></div>
      <div class="card-body">
        <div class="stat-grid">
          ${[["Target", cost.target_usd || 0], ["Evaluator", cost.evaluator_usd || 0], ["Total", cost.total_usd || 0]]
            .map(([l, v]) => `<div class="stat"><div class="stat-label">${l}</div><div class="stat-value mono">$${Number(v).toFixed(4)}</div></div>`).join("")}
        </div>
      </div>
    </section>` : "";

  const verdictPanel = verdict ? `
    <section class="card">
      <div class="card-head"><h2>Policy gate</h2>${badge(verdict.verdict)} ${verdict.overridden ? badge("warn", "overridden") : ""}</div>
      <div class="card-body">
        <table class="data">
          <thead><tr><th>Gate</th><th>Verdict</th><th>Severity</th><th>Reason</th></tr></thead>
          <tbody>${verdict.decisions.map((d) => `
            <tr>
              <td class="mono">${esc(d.gate_id)}</td>
              <td>${badge(d.verdict)}</td>
              <td>${badge(d.severity)}</td>
              <td class="cell-second">${esc(d.reason)}</td>
            </tr>`).join("")}</tbody>
        </table>
        ${verdict.override ? `<p class="cell-second mt-2 mb-0">Override: ${esc(verdict.override.reason)} by <span class="mono">${esc(verdict.override.overridden_by)}</span></p>` : ""}
      </div>
    </section>` : `
    <section class="card">
      <div class="card-head"><h2>Policy gate</h2><span class="badge badge--info">no gates configured</span></div>
      <div class="card-body"><p class="cell-second mb-0">This run is not gated — no policy gates are configured for the tenant.</p></div>
    </section>`;

  const resultsTable = tableBase(
    `<th>Metric</th><th class="num">Score</th><th>Severity</th><th>Reason</th><th></th>`,
    results.map((r) => `
      <tr>
        <td class="mono">${esc(r.metric_name)}</td>
        <td class="num">${fmtScore(r.score)}</td>
        <td>${r.severity ? badge(r.severity) : "—"}</td>
        <td class="cell-second">${esc(r.reason || "")}</td>
        <td><button class="btn btn--sm btn--ghost" data-action="open-provenance" data-id="${esc(r.id)}">Provenance</button></td>
      </tr>`),
    empty("No metric results yet.", "Results appear as executions complete."));

  const evidenceTable = tableBase(
    `<th>Evidence</th><th>Evaluator</th><th>Classification</th><th>Created</th>`,
    evidence.map((ev) => `
      <tr>
        <td class="cell-main mono">${esc(short(ev.id, 18))}<br><span class="cell-second">${esc(ev.content_type || ev.classification) || ""}</span></td>
        <td class="mono">${esc(ev.evaluator_identity)}@${esc(ev.evaluator_version)}</td>
        <td>${badge(ev.classification.replace("_", "-"), ev.classification)}</td>
        <td class="cell-second">${time(ev.created_at)}</td>
      </tr>`),
    empty("No evidence recorded for this run."));

  const tracesPanel = traces.length ? `
    <section class="card">
      <div class="card-head"><h2>Traces</h2><span class="cell-second">${traces.length} trace(s) · preserved</span></div>
      <div class="card-body">
        ${traces.map((t) => `
          <dl class="kv">
            <dt>Trace</dt><dd class="mono">${esc(t.trace_id)}</dd>
            <dt>Execution</dt><dd class="mono">${esc(t.execution_id)}</dd>
            <dt>Spans</dt><dd>${t.span_count}</dd>
          </dl>
          ${t.spans.map((s, i) => `
            <div class="span-row">
              <span class="cell-second">${i + 1}</span>
              <span class="mono">${esc(s.name)}</span>
              <span>${badge(s.status)}</span>
            </div>
            <div class="span-row" style="padding-left:40px"><span></span><span class="cell-second">${time(s.start_time)} → ${time(s.end_time)} · ${esc(jsonify(s.attributes))}</span></div>`).join("")}
        `).join("")}
      </div>
    </section>` : "";

  const poller = ["queued", "running", "retrying", "partial"].includes(run.status);
  if (poller) {
    S.poll = setTimeout(() => {
      if (location.hash === `#/run/${runId}`) navigate();
    }, 2500);
  }

  const actions = `<div class="flex flex-wrap">
    <button class="btn btn--ghost" data-action="refresh">Refresh</button>
    ${["queued", "running", "retrying", "partial"].includes(run.status)
      ? `<button class="btn btn--danger" data-action="cancel-run" data-id="${esc(run.run_id)}">Cancel run</button>` : ""}
    <button class="btn btn--subtle" data-action="nav" data-route="runs">Back to runs</button>
  </div>`;

  return `
    ${pageHead(`Run ${esc(short(run.run_id, 24))}`, `experiment <span class="mono">${esc(run.experiment_id)}</span>`, actions)}
    <div class="detail-grid">
      ${meta}
      <div class="flex flex-wrap" style="flex-direction:column;gap:12px">
        ${costPanel}${verdictPanel}
      </div>
    </div>
    <section class="card card-flush" aria-label="Metric results">
      <div class="card-head"><h2>Metric results</h2><span class="cell-second">${results.length} result(s)</span></div>
      <div class="card-body">${resultsTable}</div>
    </section>
    <section class="card card-flush" aria-label="Evidence">
      <div class="card-head"><h2>Evidence</h2><span class="cell-second">write-once · content-hashed</span></div>
      <div class="card-body">${evidenceTable}</div>
    </section>
    ${tracesPanel}`;
}

/* ---------------------------------------------------------------- catalog */

async function renderCatalog() {
  let catalog = S.catalog;
  try { catalog = await api("/catalog"); S.catalog = catalog; } catch { /* keep cache */ }

  const targetRows = tableBase(
    `<th>Name</th><th>Version</th><th>Config</th><th>Created</th>`,
    catalog.targets.map((t) => `
      <tr>
        <td class="cell-main">${esc(t.name)}<br><span class="cell-second mono">${esc(short(t.id, 18))}</span></td>
        <td class="mono">${esc(t.label)} ${t.referenced ? badge("locked", "referenced") : ""}</td>
        <td class="cell-second"><button class="btn btn--sm btn--subtle" data-action="preview-config" data-data='${esc(JSON.stringify({ title: t.name + " — target config", config: t.config }))}'>View config</button></td>
        <td class="cell-second">${time(t.created_at)}</td>
      </tr>`),
    empty("No targets registered.", "Register the application you want to evaluate.", `<button class="btn btn--primary btn--sm" data-action="register-target">Register target</button>`));

  const datasetRows = tableBase(
    `<th>Name</th><th>Version</th><th>Status</th><th>Cases</th><th>Created</th>`,
    catalog.datasets.map((d) => `
      <tr>
        <td class="cell-main">${esc(d.name)}<br><span class="cell-second mono">${esc(short(d.id, 18))}</span></td>
        <td class="mono">${esc(d.label)}</td>
        <td>${badge(d.status)}</td>
        <td class="num">${d.test_case_count}</td>
        <td class="cell-second">${time(d.created_at)}</td>
      </tr>`),
    empty("No datasets registered.", "Register the labeled test set you want to score against.", `<button class="btn btn--primary btn--sm" data-action="register-dataset">Register dataset</button>`));

  return `
    ${pageHead("Catalog", "Registered targets and datasets — the versions experiments pin.",
      `<button class="btn btn--primary" data-action="register-target">Register target</button>
       <button class="btn btn--ghost" data-action="register-dataset">Register dataset</button>
       <button class="btn btn--ghost" data-action="refresh">Refresh</button>`)}
    <section class="card card-flush">
      <div class="card-head"><h2>Targets</h2><span class="cell-second">${catalog.targets.length} version(s)</span></div>
      <div class="card-body">${targetRows}</div>
    </section>
    <section class="card card-flush">
      <div class="card-head"><h2>Datasets</h2><span class="cell-second">${catalog.datasets.length} version(s)</span></div>
      <div class="card-body">${datasetRows}</div>
    </section>`;
}

/* ---------------------------------------------------------------- analysis */

async function renderAnalysis() {
  const runs = S.runs;
  if (!runs.length) {
    return `${pageHead("Analysis", "Trend, regression, compare and failure clustering across runs.", "")}
      ${empty("Not enough data.", "Run an evaluation first; analysis needs at least one completed run.")}`;
  }

  const metricOptions = [...S.metricNames];
  if (!metricOptions.length) {
    const results = await api(`/runs/${encodeURIComponent(runs[0].run_id)}/results`).catch(() => []);
    results.forEach((r) => S.metricNames.add(r.metric_name));
  }
  const metrics = [...S.metricNames];
  const metric = metrics[0] || "exact_match";

  const fmtRun = (r) => {
    const exp = S.experiments.find((e) => e.id === r.experiment_id) || {};
    return `${exp.name ? exp.name + " · " : ""}${short(r.run_id, 12)} · ${r.status}`;
  };

  const runOptions = runs.map((r) => `<option value="${esc(r.run_id)}">${esc(fmtRun(r))}</option>`).join("");

  const baseline = runs.find((r) => ["succeeded", "partial"].includes(r.status));
  const current = runs.find((r) => r !== baseline && r.run_id !== (baseline && baseline.run_id));

  let regressionHtml = `<div class="empty">Pick a baseline and current run to detect regressions.</div>`;
  let trendHtml = `<div class="empty">Pick a metric to see its trend.</div>`;
  let failureHtml = `<div class="empty">Pick runs to cluster failures.</div>`;

  if (baseline && current) {
    const [reg, trend, failures] = await Promise.all([
      api(`/analysis/regression?baseline_run_id=${encodeURIComponent(baseline.run_id)}&current_run_id=${encodeURIComponent(current.run_id)}`).catch(() => null),
      api(`/analysis/trend/${encodeURIComponent(metric)}?run_ids=${runs.slice(0, 8).map((r) => encodeURIComponent(r.run_id)).join("&run_ids=")}`).catch(() => null),
      api(`/analysis/failures?run_ids=${runs.slice(0, 8).map((r) => encodeURIComponent(r.run_id)).join("&run_ids=")}`).catch(() => null),
    ]);

    if (reg) {
      const items = Array.isArray(reg) ? reg : reg.metrics || [reg];
      regressionHtml = tableBase(
        `<th>Metric</th><th class="num">Baseline</th><th class="num">Current</th><th class="num">Δ</th><th class="num">p-value</th><th>Direction</th>`,
        items.map((m) => `
          <tr>
            <td class="mono">${esc(m.metric_name || m.metric || "—")}</td>
            <td class="num">${fmtScore(m.baseline_score != null ? m.baseline_score : m.baseline)}</td>
            <td class="num">${fmtScore(m.current_score != null ? m.current_score : m.current)}</td>
            <td class="num">${fmtScore(m.delta != null ? m.delta : (m.change == null ? "—" : m.change))}</td>
            <td class="num">${m.p_value != null ? Number(m.p_value).toFixed(4) : "—"}</td>
            <td>${badge(m.direction == null ? "info" : (String(m.direction).toLowerCase().includes("regress") ? "fail" : "pass"), m.direction || "no change")}</td>
          </tr>`),
        `<div class="empty">Regression: no significant change detected.</div>`);
    } else {
      regressionHtml = `<div class="empty">Regression endpoint returned no data (422 usually means insufficient samples).</div>`;
    }

    if (trend && trend.data_points && trend.data_points.length) {
      const pts = trend.data_points;
      const max = Math.max(...pts.map((p) => p.score), 1);
      const min = Math.min(...pts.map((p) => p.score), 0);
      const range = max - min || 1;
      const w = 480, h = 90;
      const step = w / Math.max(pts.length - 1, 1);
      const coords = pts.map((p, i) => `${(i * step).toFixed(1)},${(h - 8 - ((p.score - min) / range) * (h - 16)).toFixed(1)}`);
      trendHtml = `
        <div class="card-body">
          <div class="flex flex-wrap" style="justify-content:space-between">
            <span>${badge(trend.overall_trend)} overall <span class="cell-second">(${pts.length} points)</span></span>
          </div>
          <svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Trend for ${esc(metric)}" style="width:100%;height:auto">
            <polyline points="${coords.join(" ")}" fill="none" stroke="var(--accent)" stroke-width="2"/>
            ${pts.map((p, i) => `<circle cx="${(i * step).toFixed(1)}" cy="${(h - 8 - ((p.score - min) / range) * (h - 16)).toFixed(1)}" r="2.5" fill="var(--accent-strong)"/>`).join("")}
          </svg>
          <div class="cell-second" style="font-size:11px">Analyzed ${time(trend.analyzed_at)}</div>
        </div>`;
    }

    if (failures) {
      const clusters = Array.isArray(failures) ? failures : (failures.clusters || []);
      failureHtml = clusters.length ? tableBase(
        `<th>Cluster</th><th class="num">Count</th><th>Examples</th>`,
        clusters.map((c) => `
          <tr>
            <td class="mono">${esc(c.label || c.cluster || "—")}</td>
            <td class="num">${c.count}</td>
            <td class="cell-second mono">${(c.example_ids || c.examples || []).slice(0, 3).map(esc).join(", ") || "—"}</td>
          </tr>`),
        `<div class="empty">No failure clusters — no critical failures in the selected runs.</div>`) : `<div class="empty">No failure clusters found.</div>`;
    }
  }

  return `
    ${pageHead("Analysis", "Statistical comparison of runs: regressions, trends, failure clusters.", "")}
    <section class="card">
      <div class="card-head"><h2>Regression (baseline vs. current)</h2></div>
      <div class="card-body">
        <div class="field-row cols-2">
          <label class="field"><span class="field-label">Baseline run</span>
            <select class="select" id="an-baseline">${runOptions}</select></label>
          <label class="field"><span class="field-label">Current run</span>
            <select class="select" id="an-current">${runOptions}</select></label>
        </div>
        <div class="mt-2"><button class="btn btn--primary" data-action="analysis-run">Analyze</button></div>
      </div>
      <div class="card-body">${regressionHtml}</div>
    </section>
    <div class="detail-grid">
      <section class="card card-flush" aria-label="Trend">
        <div class="card-head"><h2>Trend</h2>
          <select class="select" id="an-metric" style="max-width:220px">
            ${metrics.map((m) => `<option value="${esc(m)}" ${m === metric ? "selected" : ""}>${esc(m)}</option>`).join("")}
          </select></div>
        ${trendHtml}
      </section>
      <section class="card card-flush" aria-label="Failure clusters">
        <div class="card-head"><h2>Failure clusters</h2></div>
        <div class="card-body">${failureHtml}</div>
      </section>
    </div>`;
}

/* ---------------------------------------------------------------- audit */

async function renderAudit() {
  const f = $("#audit-filter") ? $("#audit-filter").value : "";
  let entries = await api("/security/audit").catch(() => []);
  if (f) entries = entries.filter((e) => (e.action || "").includes(f));
  if (!entries.length) {
    return `${pageHead("Audit", "Append-only trail of every security-relevant action.", "")}
      ${empty("No audit entries yet.", "Actions like experiment creation and run submission appear here.")}`;
  }
  const rows = entries.map((e) => `
    <tr>
      <td class="cell-second">${time(e.timestamp)}</td>
      <td class="mono">${esc(e.action)}</td>
      <td class="cell-second mono">${esc(e.actor_id)}</td>
      <td class="cell-second">${esc(e.resource_type)}</td>
      <td class="cell-second mono">${esc(e.resource_id || "")}</td>
    </tr>`);
  return `
    ${pageHead("Audit", "Append-only trail of every security-relevant action.", "")}
    <section class="card card-flush">
      <div class="toolbar" style="padding:10px 14px">
        <input class="input grow" id="audit-filter" data-action="filter" placeholder="Filter by action (e.g. run., experiment., gate.)…" aria-label="Filter audit trail" />
      </div>
      ${tableBase(
        `<th>Timestamp</th><th>Action</th><th>Actor</th><th>Resource</th><th>Resource id</th>`,
        rows,
        empty("No audit entries match."))}
    </section>`;
}

/* ---------------------------------------------------------------- system */

async function renderSystem() {
  let health = null;
  try { health = await api("/health/live"); } catch { /* offline */ }

  const checks = health ? health.checks.map((c) => `
    <tr>
      <td class="mono">${esc(c.name)}</td>
      <td>${badge(c.status)}</td>
      <td class="cell-second">${esc(c.detail || "")}</td>
    </tr>`).join("") : `<tr><td class="empty">Health endpoint unreachable without authentication.</td></tr>`;

  return `
    ${pageHead("System", "Health, security tools, and programmatic access.", "")}
    <section class="card card-flush" aria-label="Health">
      <div class="card-head"><h2>Health</h2>${health ? badge(health.overall) : badge("error", "unreachable")}</div>
      <div class="card-body"><div class="table-wrap"><table class="data">
        <thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>${checks}</tbody>
      </table></div></div>
    </section>
    <section class="card" aria-label="PII redaction tool">
      <div class="card-head"><h2>PII redaction</h2></div>
      <div class="card-body">
        <p class="cell-second" style="margin-top:0">Redact emails, phones, and credit-card spans from free text before it leaves your systems.</p>
        <label class="field"><span class="field-label">Text</span>
          <textarea class="input" id="pii-input" rows="4" placeholder="My email is jane@example.com and my phone is +1 555 010 9999."></textarea></label>
        <div class="mt-2"><button class="btn btn--primary" data-action="pii-redact">Redact</button></div>
        <div id="pii-out" class="mt-2"></div>
      </div>
    </section>
    <section class="card">
      <div class="card-head"><h2>Programmatic access</h2></div>
      <div class="card-body">
        <dl class="kv">
          <dt>Swagger</dt><dd><a href="/docs" target="_blank" rel="noreferrer">/docs</a></dd>
          <dt>OpenAPI</dt><dd><a href="/openapi.json" target="_blank" rel="noreferrer">/openapi.json</a></dd>
          <dt>CLI</dt><dd class="mono">aegis version | probe | evaluate | record | worker | serve</dd>
          <dt>Auth</dt><dd class="cell-second">Bearer tokens are HMAC-signed (<span class="mono">aegis.v1.&lt;payload&gt;.&lt;sig&gt;</span>). Dev login is served at <span class="mono">GET /security/dev-token</span> when <span class="mono">AEGIS_DEV_LOGIN=1</span>.</dd>
        </dl>
      </div>
    </section>`;
}

/* ---------------------------------------------------------------- login fallback */

function renderLogin(detail, status) {
  return `
    <div class="login-screen">
      <div class="warn-banner"><strong>Dashboard login unavailable</strong>
        <div>The API rejected the handshake <span class="mono">(${status}, ${esc(detail)})</span>.<br>
        The dashboard authenticates through the dev-login endpoint. Start the API with
        <span class="mono">AEGIS_DEV_LOGIN=1</span> in development:<br>
        <pre class="code">AEGIS_DEV_LOGIN=1 docker compose up -d --build api</pre>
        The REST API stays fully available at <a href="/docs">/docs</a> with a manually sourced bearer token.</div>
      </div>
      <div><button class="btn btn--primary" data-action="retry-login">Retry login</button></div>
    </div>`;
}

/* ---------------------------------------------------------------- forms */

function newExperimentModal() {
  const targets = S.catalog.targets;
  const datasets = S.catalog.datasets;
  const targetOptions = targets.length
    ? targets.map((t) => `<option value="${esc(t.id)}">${esc(t.name)} · v${esc(t.label)} · ${esc(short(t.id, 10))}</option>`).join("")
    : `<option value="">No targets registered</option>`;
  const datasetOptions = datasets.length
    ? datasets.map((d) => `<option value="${esc(d.id)}">${esc(d.name)} · v${esc(d.label)} (${d.test_case_count} cases)</option>`).join("")
    : `<option value="">No datasets registered</option>`;

  openModal({
    title: "New experiment",
    body: `
      <p class="cell-second" style="margin:0">An experiment pins an immutable snapshot: one target version, one dataset version, and the evaluators to run. Register them in <a href="#/catalog">Catalog</a> if they are missing.</p>
      <div class="field-row cols-2">
        <label class="field"><span class="field-label">Name</span>
          <input class="input" id="exp-name" placeholder="cli-qa" required autocomplete="off" /></label>
        <label class="field"><span class="field-label">Project id</span>
          <input class="input" id="exp-project" value="prj:1" required autocomplete="off" /></label>
      </div>
      <div class="field-row cols-2">
        <label class="field"><span class="field-label">Target version</span>
          <select class="select" id="exp-target">${targetOptions}</select></label>
        <label class="field"><span class="field-label">Dataset version</span>
          <select class="select" id="exp-dataset">${datasetOptions}</select></label>
      </div>
      <label class="field"><span class="field-label">Evaluators</span>
        <input class="input" id="exp-evaluators" value="${DEFAULT_EVALUATOR}" autocomplete="off" />
        <span class="field-hint">Comma-separated evaluator ids. Default is deterministic exact-match.</span></label>
      <label class="field"><span class="field-label">Policy version id <span class="cell-second">(optional)</span></span>
        <input class="input" id="exp-policy" placeholder="none" autocomplete="off" /></label>
      <div id="exp-error" class="field-error hidden"></div>`,
    actions: `
      <button class="btn btn--subtle" data-action="modal-close">Cancel</button>
      <button class="btn btn--primary" data-action="create-experiment">Create experiment</button>`,
  });
}

function registerTargetModal() {
  openModal({
    title: "Register target",
    body: `
      <p class="cell-second" style="margin:0">A target is the application under evaluation. Config is passed to the evaluation engine on run; point it at a reachable <span class="mono">POST /invoke</span> endpoint.</p>
      <div class="field-row cols-2">
        <label class="field"><span class="field-label">Name</span><input class="input" id="tgt-name" placeholder="my-app" required /></label>
        <label class="field"><span class="field-label">Project id</span><input class="input" id="tgt-project" value="prj:1" required /></label>
      </div>
      <div class="field-row cols-2">
        <label class="field"><span class="field-label">Target type</span>
          <select class="select" id="tgt-type">
            <option value="llm_application">llm_application</option>
            <option value="rag_pipeline">rag_pipeline</option>
            <option value="agent">agent</option>
            <option value="multi_agent">multi_agent</option>
            <option value="model_api">model_api</option>
            <option value="classifier">classifier</option>
          </select></label>
        <label class="field"><span class="field-label">Version label</span><input class="input" id="tgt-label" value="1.0.0" required /><span class="field-hint">SemVer.</span></label>
      </div>
      <label class="field"><span class="field-label">Config (JSON)</span>
        <textarea class="input" id="tgt-config" rows="4" placeholder='{"base_url": "http://localhost:8080", "invoke_path": "/invoke"}'></textarea>
        <span class="field-hint">Inside Docker, use the container name, e.g. <span class="mono">http://my-app:8080</span>.</span></label>
      <div id="tgt-error" class="field-error hidden"></div>`,
    actions: `
      <button class="btn btn--subtle" data-action="modal-close">Cancel</button>
      <button class="btn btn--primary" data-action="create-target">Register</button>`,
  });
}

function registerDatasetModal() {
  openModal({
    title: "Register dataset",
    body: `
      <p class="cell-second" style="margin:0">A dataset is a labeled test set: inputs paired with golden expectations. One or more test cases become a draft version.</p>
      <div class="field-row cols-2">
        <label class="field"><span class="field-label">Name</span><input class="input" id="ds-name" placeholder="qa-echo" required /></label>
        <label class="field"><span class="field-label">Project id</span><input class="input" id="ds-project" value="prj:1" required /></label>
      </div>
      <div class="field-row cols-2">
        <label class="field"><span class="field-label">Version label</span><input class="input" id="ds-label" value="1.0.0" required /></label>
      </div>
      <label class="field"><span class="field-label">Test cases (JSON)</span>
        <textarea class="input" id="ds-cases" rows="6" placeholder='[{"input": "hello", "expected": "hello"}]'></textarea>
        <span class="field-hint">Array of <span class="mono">{"input": ..., "expected": ..., "metadata": {}}</span>.</span></label>
      <div id="ds-error" class="field-error hidden"></div>`,
    actions: `
      <button class="btn btn--subtle" data-action="modal-close">Cancel</button>
      <button class="btn btn--primary" data-action="create-dataset">Register</button>`,
  });
}

function submitRunModal(expId) {
  const exp = S.experiments.find((e) => e.id === expId);
  const key = (crypto.randomUUID && crypto.randomUUID()) || `${Date.now()}-${Math.random()}`;
  openModal({
    title: `Submit run · ${exp ? esc(exp.name) : expId}`,
    body: `
      <p class="cell-second" style="margin:0">The run is enqueued and executed by an engine worker. Replays of the same idempotency key return the original run instead of creating a duplicate.</p>
      <label class="field"><span class="field-label">Idempotency key</span>
        <input class="input mono" id="run-key" data-exp="${esc(expId)}" value="${esc(key)}" /></label>
      <div id="run-error" class="field-error hidden"></div>`,
    actions: `
      <button class="btn btn--subtle" data-action="modal-close">Cancel</button>
      <button class="btn btn--primary" data-action="create-run">Submit run</button>`,
  });
}

/* ---------------------------------------------------------------- actions */

async function onAction(ev) {
  const el = ev.target.closest("[data-action]");
  if (!el) return;
  const action = el.dataset.action;
  const id = el.dataset.id || el.dataset.route;

  if (action === "nav") { ev.preventDefault(); push(id); return; }
  if (action === "modal-close") { closeModal(); return; }

  if (action === "confirm") {
    closeModal();
    if (rootConfirm) rootConfirm();
    rootConfirm = null;
    return;
  }

  if (action === "retry-login") {
    setAuth("pending", "connecting…");
    await boot();
    return;
  }

  if (!S.token) { toast("Not authenticated", "Dev login is unavailable.", "error"); return; }

  switch (action) {
    case "refresh": case "filter":
      try { await refreshAll(); navigate(); } catch (err) { toast("Refresh failed", err.message, "error"); }
      break;
    case "open-experiment":
      push(`experiment/${id}`);
      break;
    case "open-run":
      push(`run/${id}`);
      break;
    case "new-experiment":
      newExperimentModal();
      break;
    case "register-target":
      registerTargetModal();
      break;
    case "register-dataset":
      registerDatasetModal();
      break;
    case "preview-config": {
      const data = JSON.parse(el.dataset.data);
      openModal({ title: data.title, body: `<pre class="code">${esc(jsonify(data.config))}</pre>`,
        actions: `<button class="btn btn--subtle" data-action="modal-close">Close</button>` });
      break;
    }
    case "open-provenance": {
      toast("Fetching provenance…", "", "warn");
      try {
        const prov = await api(`/evidence/provenance/${encodeURIComponent(id)}`);
        openModal({ title: "Provenance", body: `<pre class="code">${esc(jsonify(prov))}</pre>`,
          actions: `<button class="btn btn--subtle" data-action="modal-close">Close</button>` });
      } catch (err) { toast("Provenance unavailable", err.message, "error"); }
      break;
    }
    case "create-experiment":
      return createExperimentFromForm();
    case "create-target":
      return createTargetFromForm();
    case "create-dataset":
      return createDatasetFromForm();
    case "create-run":
      return createRunFromForm();
    case "submit-run":
      submitRunModal(id);
      break;
    case "start-experiment":
      confirmDialog({
        title: "Start experiment",
        message: "Starting locks the immutable snapshot. Continue?",
        confirmLabel: "Start",
        kind: "primary",
        onConfirm: async () => {
          try {
            const exp = await api(`/experiments/${encodeURIComponent(id)}/start`, { method: "POST" });
            toast(`Experiment ${short(exp.id)} started`, "", "success");
            await refreshAll(); navigate();
          } catch (err) { toast("Failed to start", err.message, "error"); }
        },
      });
      break;
    case "clone-experiment":
      try {
        const exp = await api(`/experiments/${encodeURIComponent(id)}/clone`, { method: "POST" });
        toast("Cloned as comparison variant", short(exp.id), "success");
        await refreshAll(); navigate();
      } catch (err) { toast("Failed to clone", err.message, "error"); }
      break;
    case "cancel-run":
      confirmDialog({
        title: "Cancel run?",
        message: `Request cooperative cancellation of ${id}. In-flight executions will stop at the next safe point.`,
        confirmLabel: "Cancel run",
        onConfirm: async () => {
          try {
            const run = await api(`/runs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
            toast("Cancellation requested", run.status, "success");
            await refreshAll(); navigate();
          } catch (err) { toast("Failed to cancel", err.message, "error"); }
        },
      });
      break;
    case "analysis-run": {
      const base = $("#an-baseline").value;
      const cur = $("#an-current").value;
      if (!base || !cur || base === cur) { toast("Choose two different runs", "", "warn"); return; }
      try {
        const reg = await api(`/analysis/regression?baseline_run_id=${encodeURIComponent(base)}&current_run_id=${encodeURIComponent(cur)}`);
        toast("Regression analyzed", "", "success");
      } catch (err) { toast("Regression failed", err.message, "error"); }
      break;
    }
    case "pii-redact": {
      const text = $("#pii-input").value;
      if (!text.trim()) { toast("Enter text to redact", "", "warn"); return; }
      try {
        const out = await api("/security/pii/redact", { method: "POST", json: { text } });
        $("#pii-out").innerHTML = `
          <label class="field"><span class="field-label">Redacted</span>
            <pre class="code">${esc(out.redacted)}</pre></label>
          ${out.pii_spans.length ? `<table class="data"><thead><tr><th>Type</th><th>Span</th><th>Masked</th></tr></thead>
            <tbody>${out.pii_spans.map((s) => `<tr><td>${badge("warn", s.pii_type)}</td><td class="num">${s.start}–${s.end}</td><td class="mono">${esc(s.redacted_value)}</td></tr>`).join("")}</tbody></table>` : ""}`;
        toast(`Redacted ${out.pii_spans.length} PII span(s)`, "", "success");
      } catch (err) { toast("Redaction failed", err.message, "error"); }
      break;
    }
  }
}

async function createExperimentFromForm() {
  const errBox = $("#exp-error");
  errBox.classList.add("hidden");
  const name = $("#exp-name").value.trim();
  const project = $("#exp-project").value.trim();
  const target = $("#exp-target").value;
  const dataset = $("#exp-dataset").value;
  const evaluators = $("#exp-evaluators").value.split(",").map((s) => s.trim()).filter(Boolean);
  const policy = $("#exp-policy").value.trim() || null;

  if (!name || !project) { errBox.textContent = "Name and project id are required."; errBox.classList.remove("hidden"); return; }
  if (!target || !dataset) { errBox.textContent = "Register a target and dataset in the catalog first."; errBox.classList.remove("hidden"); return; }

  try {
    const exp = await api("/experiments", { method: "POST", json: {
      name, project_id: project,
      snapshot: { target_version_id: target, dataset_version_id: dataset, evaluator_version_ids: evaluators, policy_version_id: policy, settings: {} },
    }});
    closeModal();
    toast("Experiment created", short(exp.id), "success");
    await refreshAll();
    push(`experiment/${exp.id}`);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  }
}

async function createTargetFromForm() {
  const errBox = $("#tgt-error");
  errBox.classList.add("hidden");
  const name = $("#tgt-name").value.trim();
  const project = $("#tgt-project").value.trim();
  const type = $("#tgt-type").value;
  const label = $("#tgt-label").value.trim();
  let config = {};
  try { config = JSON.parse($("#tgt-config").value || "{}"); }
  catch { errBox.textContent = "Config must be valid JSON."; errBox.classList.remove("hidden"); return; }
  if (!name || !project) { errBox.textContent = "Name and project id are required."; errBox.classList.remove("hidden"); return; }

  const btn = document.querySelector('[data-action="create-target"]');
  btn.disabled = true;
  try {
    const t = await api("/catalog/targets", { method: "POST", json: { project_id: project, name, target_type: type, label, config } });
    closeModal();
    toast("Target registered", short(t.id), "success");
    await refreshAll(); navigate();
  } catch (err) {
    btn.disabled = false;
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  }
}

async function createDatasetFromForm() {
  const errBox = $("#ds-error");
  errBox.classList.add("hidden");
  const name = $("#ds-name").value.trim();
  const project = $("#ds-project").value.trim();
  const label = $("#ds-label").value.trim();
  let cases = [];
  try { cases = JSON.parse($("#ds-cases").value || "[]"); }
  catch { errBox.textContent = "Test cases must be valid JSON."; errBox.classList.remove("hidden"); return; }
  if (!Array.isArray(cases)) { errBox.textContent = "Test cases must be a JSON array."; errBox.classList.remove("hidden"); return; }
  if (!name || !project) { errBox.textContent = "Name and project id are required."; errBox.classList.remove("hidden"); return; }

  const btn = document.querySelector('[data-action="create-dataset"]');
  btn.disabled = true;
  try {
    const d = await api("/catalog/datasets", { method: "POST", json: { project_id: project, name, label, test_cases: cases } });
    closeModal();
    toast("Dataset registered", `${d.test_case_count} test case(s)`, "success");
    await refreshAll(); navigate();
  } catch (err) {
    btn.disabled = false;
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  }
}

async function createRunFromForm() {
  const errBox = $("#run-error");
  const key = $("#run-key").value.trim();
  const expId = $("#run-key").dataset.exp;
  errBox.classList.add("hidden");
  if (!expId) { toast("Missing experiment id", "", "error"); closeModal(); return; }
  try {
    const run = await api("/runs", { method: "POST", json: { experiment_id: expId, idempotency_key: key } });
    closeModal();
    toast("Run submitted", run.run_id, "success");
    await refreshAll();
    push(`run/${run.run_id}`);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  }
}

function onKey(ev) {
  if (ev.key === "Escape") closeModal();
  if (ev.key.toLowerCase() === "n" && (ev.metaKey || ev.ctrlKey) && S.token) {
    ev.preventDefault();
    newExperimentModal();
  }
}

/* ---------------------------------------------------------------- start */

$("#quick-new").addEventListener("click", () => { if (S.token) newExperimentModal(); });
setTimeout(boot, 30);