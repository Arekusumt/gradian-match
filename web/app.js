"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const num = (x) => Number(x) || 0;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = (path, body) => fetch(path, {
  method: body ? "POST" : "GET",
  headers: { "Content-Type": "application/json" },
  body: body ? JSON.stringify(body) : undefined,
}).then((r) => r.json());
const srcFrom = (t) => (/^https?:\/\//i.test(t.trim()) ? { kind: "url", value: t.trim() } : { kind: "text", value: t });
let lastResume = null;

/* ── theme ─────────────────────────────────────────────────────────── */
function applyTheme(t) {
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  else document.documentElement.removeAttribute("data-theme");
}
$("#theme").onclick = () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : cur === "light" ? "dark"
    : (matchMedia("(prefers-color-scheme: dark)").matches ? "light" : "dark");
  localStorage.setItem("gm-theme", next); applyTheme(next);
};

/* ── tabs ──────────────────────────────────────────────────────────── */
$$(".tab").forEach((t) => t.addEventListener("click", () => {
  if (t.disabled) return;
  $$(".tab").forEach((x) => x.classList.remove("active"));
  $$(".pane").forEach((x) => x.classList.remove("active"));
  t.classList.add("active");
  $("#" + t.dataset.tab).classList.add("active");
}));

/* ── SSE over fetch (POST) ─────────────────────────────────────────── */
async function streamRun(path, body, onEvent) {
  const resp = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!resp.ok || !resp.body) {
    let j = {}; try { j = await resp.json(); } catch (_) {}
    onEvent({ type: "error", message: j.error || ("HTTP " + resp.status) });
    onEvent({ type: "done" });
    return;
  }
  const reader = resp.body.getReader(), dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data:")) {
          const d = line.slice(5).trim();
          if (d) { try { onEvent(JSON.parse(d)); } catch (_) {} }
        }
      }
    }
  }
}

/* ── the agent console (signature element) ─────────────────────────── */
const GLYPH = { extract: "❏", analyst: "◎", tailor: "✂", critic: "✓", examiner: "◉", verifier: "❖" };
function makeConsole(el) {
  el.classList.remove("hidden");
  el.innerHTML = `<div class="head"><b>Agents at work</b><span class="pctnum">0%</span></div>
    <div class="bar"><i></i></div><div class="rows"></div>`;
  const bar = el.querySelector(".bar > i"), pct = el.querySelector(".pctnum"), rows = el.querySelector(".rows");
  const map = {};
  const setPct = (p) => { if (typeof p === "number") { bar.style.width = p + "%"; pct.textContent = p + "%"; } };
  return {
    start(agents) {
      rows.innerHTML = "";
      (agents || []).forEach((a) => {
        const d = document.createElement("div");
        d.className = "agent"; d.dataset.st = "queued";
        d.innerHTML = `<div class="ava">${esc(GLYPH[a.id] || "●")}</div>
          <div><div class="who">${esc(a.name)}</div><div class="lbl">${esc(a.desc || "waiting…")}</div></div>
          <div class="st">queued</div>`;
        rows.appendChild(d); map[a.id] = d;
      });
    },
    agent(e) {
      const d = map[e.agent]; if (!d) return;
      d.dataset.st = e.status;
      d.querySelector(".st").textContent = e.status;
      if (e.label) d.querySelector(".lbl").textContent = e.label;
      setPct(e.pct);
    },
    finish() { setPct(100); },
  };
}
function runWithConsole(path, body, consoleEl) {
  const con = makeConsole(consoleEl);
  return new Promise((resolve, reject) => {
    let result = null, err = null;
    streamRun(path, body, (e) => {
      if (e.type === "start") con.start(e.agents);
      else if (e.type === "agent") con.agent(e);
      else if (e.type === "result") result = e.data;
      else if (e.type === "error") err = e.message || "failed";
      else if (e.type === "done") { con.finish(); err ? reject(new Error(err)) : resolve(result); }
    }).catch(reject);
  });
}
function errorCard(el, msg) { el.classList.remove("hidden"); el.innerHTML = `<p class="error">⚠ ${esc(msg)}</p>`; }

/* ── file upload + real PDF preview ────────────────────────────────── */
async function handleFile(input, textarea, nameEl, pdfWrap) {
  const f = input.files[0]; if (!f) return;
  nameEl.textContent = f.name;
  const isPdf = f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
  if (isPdf) {
    pdfWrap.querySelector("iframe").src = URL.createObjectURL(f);
    pdfWrap.classList.remove("hidden");
  } else { pdfWrap.classList.add("hidden"); }
  const fd = new FormData(); fd.append("file", f);
  const prev = textarea.value; textarea.value = "Reading…";
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd }).then((x) => x.json());
    if (r.error) { textarea.value = prev; alert("Upload failed: " + r.error); }
    else textarea.value = r.text;
  } catch (_) { textarea.value = prev; alert("Upload failed."); }
}
$("#cv-file").addEventListener("change", (e) => handleFile(e.target, $("#cv"), $("#cv-name"), $("#cv-pdf")));
$("#offer-file").addEventListener("change", (e) => handleFile(e.target, $("#offer"), $("#offer-name"), $("#offer-pdf")));

/* ── aggressiveness slider ─────────────────────────────────────────── */
const AGG_NOTE = (v) => v <= 30
  ? "Conservative: reorders and rephrases to the offer. No new claims."
  : v <= 70 ? "Assertive: stronger verbs, surfaces defensible skills from your real experience."
  : "Aggressive: may add plausible claims to maximize the match — each one is flagged in the ledger to verify.";
$("#agg").addEventListener("input", (e) => { $("#agg-val").textContent = e.target.value; $("#agg-note").textContent = AGG_NOTE(+e.target.value); });

/* ── applier: analyze ──────────────────────────────────────────────── */
function catBar(c) {
  return `<div class="cat"><span class="n">${esc(c.name)}</span>
    <div class="track"><i style="width:${num(c.score_0_100)}%"></i></div>
    <b class="sc">${num(c.score_0_100)}</b><small>${esc(c.details || "")}</small></div>`;
}
function renderReport(rep) {
  const el = $("#report"); el.classList.remove("hidden");
  el.innerHTML = `<h3><span class="big">${num(rep.overall)}%</span> compatible</h3>
    ${(rep.categories || []).map(catBar).join("")}
    <div style="margin-top:10px"><span class="eyebrow">Matched</span>
      <div class="chips">${(rep.matched_keywords || []).map((k) => `<span class="chip good">${esc(k)}</span>`).join("") || "<small>—</small>"}</div></div>
    <div><span class="eyebrow">Missing</span>
      <div class="chips">${(rep.missing_keywords || []).map((k) => `<span class="chip miss">${esc(k)}</span>`).join("") || "<small>—</small>"}</div></div>
    ${(rep.suggestions || []).length ? `<div style="margin-top:8px"><span class="eyebrow">Do next</span><ul class="doo">${rep.suggestions.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></div>` : ""}`;
}
$("#analyze").addEventListener("click", async () => {
  const cv = $("#cv").value.trim(), offer = $("#offer").value.trim();
  if (!cv || !offer) return alert("Paste your CV and a job offer first.");
  const btn = $("#analyze"); btn.disabled = true; $("#report").classList.add("hidden");
  try { renderReport(await runWithConsole("/api/analyze/stream", { cv: srcFrom(cv), offer: srcFrom(offer) }, $("#console"))); }
  catch (e) { errorCard($("#report"), e.message); }
  finally { btn.disabled = false; }
});

/* ── applier: job finder ───────────────────────────────────────────── */
$("#find-jobs").addEventListener("click", async () => {
  const ids = $$("#platforms input:checked").map((i) => i.value);
  const btn = $("#find-jobs"); btn.disabled = true;
  try {
    const jobs = await api("/api/jobs", { cv_text: $("#cv").value, conditions: $("#conditions").value, platform_ids: ids });
    const el = $("#jobs"); el.classList.remove("hidden");
    if (jobs.error) return errorCard(el, jobs.error);
    el.innerHTML = `<div class="eyebrow" style="margin-bottom:8px">${jobs.length} matching offers</div>` +
      jobs.slice(0, 25).map((j) => `<div class="job"><span class="pc">${num(j.score)}%</span>
        <a href="${esc(j.url)}" target="_blank" rel="noopener noreferrer">${esc(j.title)}</a>
        <small>${esc(j.company)} · ${esc(j.location)} · ${esc(j.source)}</small>
        <button class="btn sm use" style="margin-left:auto" data-d="${encodeURIComponent(j.description || "")}">Analyze</button></div>`).join("");
    $$("#jobs .use").forEach((b) => b.addEventListener("click", () => { $("#offer").value = decodeURIComponent(b.dataset.d); $("#analyze").click(); window.scrollTo({ top: 0, behavior: "smooth" }); }));
  } catch (e) { errorCard($("#jobs"), e.message); }
  finally { btn.disabled = false; }
});

/* ── applier: regenerate ───────────────────────────────────────────── */
async function renderRegen(out) {
  const led = (out.ledger && out.ledger.length)
    ? `<div class="ledger"><b>⚠ Verify before you send — claims this added:</b><ul class="doo">${out.ledger.map((l) => `<li>${esc(l.claim)} — <span class="mono" style="color:var(--muted)">${esc(l.why)}</span></li>`).join("")}</ul></div>`
    : `<p class="ok">✓ No unverified claims added — everything is grounded in your CV.</p>`;
  const el = $("#regen-out"); el.classList.remove("hidden");
  el.innerHTML = `<h3 style="font-size:19px">Tailored CV — Critic ${num(out.critic_score)}/100 ·
      ${out.iterations} pass${out.iterations > 1 ? "es" : ""} · ${out.passed ? "<span class='ok'>passed the gate</span>" : "best effort"}</h3>
    <div class="actions"><button id="dl-pdf" class="btn primary sm">⬇ Download PDF</button></div>
    <div id="cv-out-pdf" class="pdfwrap"><div class="cap"><span>Your tailored CV</span><span class="mono">rendering…</span></div><iframe title="tailored CV"></iframe></div>
    ${led}
    <details style="margin-top:12px"><summary class="eyebrow" style="cursor:pointer">Show the raw data</summary><pre class="json">${esc(JSON.stringify(out.resume, null, 2))}</pre></details>`;
  $("#dl-pdf").onclick = downloadPdf;
  const w = $("#cv-out-pdf");
  try {
    const resp = await fetch("/api/pdf", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume: out.resume }) });
    if (resp.ok) { w.querySelector("iframe").src = URL.createObjectURL(await resp.blob()); w.querySelector(".cap .mono").textContent = "ready"; }
    else { const j = await resp.json().catch(() => ({})); w.querySelector(".cap .mono").textContent = j.error ? "needs Chrome/Edge for PDF" : "preview unavailable"; }
  } catch (_) { w.querySelector(".cap .mono").textContent = "preview unavailable"; }
}
async function downloadPdf() {
  if (!lastResume) return;
  const btn = $("#dl-pdf"); btn.disabled = true;
  try {
    const resp = await fetch("/api/pdf", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume: lastResume }) });
    if (!resp.ok) { const j = await resp.json().catch(() => ({})); return alert("PDF export failed: " + (j.error || resp.status)); }
    const a = document.createElement("a"); a.href = URL.createObjectURL(await resp.blob());
    a.download = "gradian-match-cv.pdf"; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  } finally { btn.disabled = false; }
}
$("#regen").addEventListener("click", async () => {
  const cv = $("#cv").value.trim(), offer = $("#offer").value.trim();
  if (!cv || !offer) return alert("Paste your CV and a job offer first.");
  const btn = $("#regen"); btn.disabled = true; $("#regen-out").classList.add("hidden");
  try {
    const out = await runWithConsole("/api/regenerate/stream", { cv: srcFrom(cv), offer: srcFrom(offer), aggressiveness: +$("#agg").value }, $("#regen-console"));
    lastResume = out.resume; await renderRegen(out);
  } catch (e) { errorCard($("#regen-out"), e.message); }
  finally { btn.disabled = false; }
});

/* ── recruiter: candidates ─────────────────────────────────────────── */
function addCandidate(name = "", cv = "") {
  const row = document.createElement("div");
  row.className = "candrow";
  row.innerHTML = `<div style="flex:none;width:150px"><input class="txt c-name" placeholder="name" value="${esc(name)}"></div>
    <textarea class="c-cv" rows="2" placeholder="paste this candidate's CV">${esc(cv)}</textarea>
    <button class="btn sm c-del" title="remove" style="flex:none">✕</button>`;
  row.querySelector(".c-del").onclick = () => row.remove();
  $("#cands").appendChild(row);
}
$("#add-cand").addEventListener("click", () => addCandidate());
addCandidate(); addCandidate();

function bandChip(ai) {
  if (!ai) return "";
  const b = (ai.band || "Low").toLowerCase();
  return `<span class="chip ${b}" title="${esc(ai.disclaimer || "")}">AI signals: ${esc(ai.band)}</span>`;
}
function sourceChips(sources) {
  return (sources || []).map((s) => `<span class="chip ${s.ok ? "ok" : "dead"}">${esc(s.kind)}${s.ok ? " ✓" : " ✕"}</span>`).join("");
}
function renderRanked(rows) {
  const el = $("#r-results"); el.classList.remove("hidden");
  if (!rows || !rows.length) { el.innerHTML = `<div class="panel"><p>No candidates could be scored. Check that each has a CV and that your AI is connected.</p></div>`; return; }
  el.innerHTML = `<div class="eyebrow" style="margin-bottom:6px">${rows.length} candidate${rows.length > 1 ? "s" : ""} ranked</div>` +
    rows.map((r, i) => `<div class="cand">
      <div class="rank">${i + 1}</div>
      <div>
        <div class="name">${esc(r.name || "Candidate " + (i + 1))}</div>
        <div class="chips">${bandChip(r.ai)}${sourceChips(r.sources)}</div>
        <div class="chips"><span class="eyebrow" style="align-self:center">has</span>${(r.matched || []).slice(0, 12).map((k) => `<span class="chip good">${esc(k)}</span>`).join("") || "<small>—</small>"}</div>
        <div class="chips"><span class="eyebrow" style="align-self:center">missing</span>${(r.missing || []).map((k) => `<span class="chip miss">${esc(k)}</span>`).join("") || "<small>—</small>"}</div>
        <button class="btn sm deep" data-cv="${encodeURIComponent(r._cv || "")}">Run deep AI check</button>
        <div class="deep-out mono" style="font-size:11.5px;margin-top:6px"></div>
      </div>
      <div class="score">${num(r.score)}%</div>
    </div>`).join("");
  $$("#r-results .deep").forEach((b) => b.addEventListener("click", async () => {
    const cv = decodeURIComponent(b.dataset.cv); if (!cv) return;
    const out = b.parentElement.querySelector(".deep-out");
    b.disabled = true; out.textContent = "Examining…";
    try {
      const s = await api("/api/recruiter/signals", { cv_text: cv });
      out.innerHTML = `<b>${esc(s.band)}</b> · ${num(s.score_0_100)}/100<ul class="doo">${(s.evidence || []).map((e) => `<li>${esc(e)}</li>`).join("")}</ul><div class="disclaimer">${esc(s.disclaimer)}</div>`;
    } catch (e) { out.textContent = "Failed: " + e.message; }
    finally { b.disabled = false; }
  }));
}
$("#rank").addEventListener("click", async () => {
  const offer = $("#r-offer").value.trim();
  const cands = $$("#cands .candrow").map((r) => ({
    name: r.querySelector(".c-name").value.trim(),
    cv_text: r.querySelector(".c-cv").value.trim(),
  })).filter((c) => c.cv_text);
  if (!offer) return alert("Paste the role you're hiring for.");
  if (!cands.length) return alert("Add at least one candidate CV.");
  const btn = $("#rank"); btn.disabled = true; $("#r-results").classList.add("hidden");
  try {
    const rows = await runWithConsole("/api/recruiter/rank/stream", { offer, candidates: cands }, $("#r-console"));
    // stitch each candidate's cv back in for the deep-check button (server doesn't echo it)
    rows.forEach((row) => { const m = cands.find((c) => c.name === row.name); if (m) row._cv = m.cv_text; });
    renderRanked(rows);
  } catch (e) { errorCard($("#r-results"), e.message); }
  finally { btn.disabled = false; }
});

/* ── recruiter: sourcing ───────────────────────────────────────────── */
$("#search").addEventListener("click", async () => {
  const role = $("#s-role").value.trim(), loc = $("#s-loc").value.trim(),
    lang = $("#s-lang").value.trim(), site = $("#s-site").value;
  if (!role) return alert("Enter a role to search for.");
  const btn = $("#search"); btn.disabled = true;
  try {
    const r = await api("/api/recruiter/search", { criteria: { language: lang, location: loc, keywords: [role] }, role, location: loc, site });
    const el = $("#r-search"); el.classList.remove("hidden");
    if (r.error) return errorCard(el, r.error);
    const gh = (r.github || []).map((c) => `<div class="job"><a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">@${esc(c.login)}</a>
      <small>${esc(c.name)}${c.location ? " · " + esc(c.location) : ""}</small></div>`).join("");
    el.innerHTML = `<div class="eyebrow">Run this X-ray in your own browser session (ToS-friendly)</div>
      <div class="xray" id="xray-str">${esc(r.xray)}</div>
      <button class="btn sm" id="copy-xray" style="margin-top:8px">Copy search string</button>
      ${gh ? `<div class="eyebrow" style="margin-top:14px">GitHub users (${r.github.length})</div>${gh}` : `<p style="margin-top:10px"><small>No GitHub matches (or add a language). The X-ray above still works.</small></p>`}`;
    $("#copy-xray").onclick = () => navigator.clipboard.writeText(r.xray).then(() => { $("#copy-xray").textContent = "Copied ✓"; });
  } catch (e) { errorCard($("#r-search"), e.message); }
  finally { btn.disabled = false; }
});

/* ── setup / connect-your-AI panel ─────────────────────────────────── */
function renderSetup(h) {
  const el = $("#setup");
  if (h.claude_ok) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  el.innerHTML = `<h2>Connect your AI to get started</h2>
    <p>Gradian Match runs on <b>your own AI account</b> — nothing is stored, nothing leaves your machine except the calls you make. Pick one:</p>
    <div class="opts">
      <div class="opt"><h4>Claude Code <span class="tag">recommended · no key</span></h4>
        <ol><li>Install <a href="https://claude.com/claude-code" target="_blank" rel="noopener">Claude Code</a> and sign in.</li>
        <li>Check it works: <code>claude --version</code></li><li>Reload this page.</li></ol></div>
      <div class="opt"><h4>Anthropic API key <span class="tag" style="background:var(--violet);color:#fff">faster</span></h4>
        <ol><li>Get a key at <a href="https://console.anthropic.com/" target="_blank" rel="noopener">console.anthropic.com</a>.</li>
        <li>Put <code>ANTHROPIC_API_KEY=…</code> in your <code>.env</code>.</li><li>Restart <code>start.bat</code>.</li></ol></div>
    </div>
    <p class="disclaimer" style="margin-top:12px">Current status: ${esc(h.message || "not connected")}</p>`;
}

/* ── boot ──────────────────────────────────────────────────────────── */
async function boot() {
  applyTheme(localStorage.getItem("gm-theme"));
  $("#agg-note").textContent = AGG_NOTE(50);
  let h = {};
  try { h = await api("/api/health"); } catch (_) { h = { claude_ok: false, message: "server not reachable" }; }
  const s = $("#status");
  s.textContent = h.claude_ok ? "AI ready ✓" : "AI not connected ✗";
  s.className = "statuschip " + (h.claude_ok ? "ok" : "bad");
  const b = h.backend || {};
  s.title = b.label ? `${b.label} · ${b.model || ""}` : (h.message || "");
  $("#foot-backend").textContent = b.label ? (b.label + (b.model ? " · " + b.model : "")) : "your own AI";
  renderSetup(h);
  try {
    const plats = await api("/api/platforms?side=applier");
    $("#platforms").innerHTML = (Array.isArray(plats) ? plats : []).filter((p) => p.kind === "api")
      .map((p) => `<label><input type="checkbox" value="${esc(p.id)}" ${["arbeitnow", "remotive"].includes(p.id) ? "checked" : ""}>${esc(p.label)}</label>`).join("");
  } catch (_) {}
}
boot();
