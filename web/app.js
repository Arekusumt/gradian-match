const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => (
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const api = (path, body) => fetch(path, {method: body ? "POST" : "GET",
  headers: {"Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined})
  .then(r => r.json());

function srcFrom(text) {
  const t = text.trim();
  return /^https?:\/\//i.test(t) ? {kind: "url", value: t} : {kind: "text", value: t};
}

let lastResume = null;

async function boot() {
  const h = await api("/api/health");
  const s = $("#claude-status");
  s.textContent = h.claude_ok ? "Claude Code ✓" : "Claude Code ✗";
  s.className = "status " + (h.claude_ok ? "ok" : "bad");
  if (!h.claude_ok) s.title = h.message || "";
  const plats = await api("/api/platforms?side=applier");
  $("#platforms").innerHTML = (Array.isArray(plats) ? plats : []).filter(p => p.kind === "api")
    .map(p => `<label><input type="checkbox" value="${esc(p.id)}" ${["arbeitnow","remotive"].includes(p.id)?"checked":""}>${esc(p.label)}</label>`).join(" ");
}

async function uploadTo(fileInput, targetTextarea) {
  const f = fileInput.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  const prev = targetTextarea.value; targetTextarea.value = "Uploading…";
  try {
    const r = await fetch("/api/upload", {method: "POST", body: fd}).then(r => r.json());
    if (r.error) { targetTextarea.value = prev; alert("Upload failed: " + r.error); }
    else targetTextarea.value = r.text;
  } catch (e) { targetTextarea.value = prev; alert("Upload failed"); }
}
$("#cv-file").addEventListener("change", e => uploadTo(e.target, $("#cv")));
$("#offer-file").addEventListener("change", e => uploadTo(e.target, $("#offer")));

$("#agg").addEventListener("input", e => $("#agg-val").textContent = e.target.value);

document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  if (t.disabled) return;
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
}));

function errorCard(where, msg) {
  where.classList.remove("hidden");
  where.innerHTML = `<p class="error">${esc(msg)}</p>`;
}

function catBar(c) {
  return `<div class="cat"><span>${esc(c.name)}</span><div class="bar"><i style="width:${Number(c.score_0_100)||0}%"></i></div>
    <b>${Number(c.score_0_100)||0}</b><small>${esc(c.details||"")}</small></div>`;
}

$("#analyze").addEventListener("click", async () => {
  const btn = $("#analyze"); btn.disabled = true; btn.textContent = "Analyzing…";
  try {
    const rep = await api("/api/analyze", {cv: srcFrom($("#cv").value), offer: srcFrom($("#offer").value)});
    if (rep.error || !rep.categories) { errorCard($("#report"), rep.error || "Analysis failed"); return; }
    $("#report").classList.remove("hidden");
    $("#report").innerHTML = `<h3>Compatibility: ${Number(rep.overall)||0}%</h3>
      ${rep.categories.map(catBar).join("")}
      <p><b>Matched:</b> ${rep.matched_keywords.map(esc).join(", ")||"—"}</p>
      <p><b>Missing:</b> ${rep.missing_keywords.map(esc).join(", ")||"—"}</p>
      <p><b>Do next:</b></p><ul>${rep.suggestions.map(s=>`<li>${esc(s)}</li>`).join("")}</ul>`;
  } finally { btn.disabled = false; btn.textContent = "Analyze compatibility"; }
});

$("#find-jobs").addEventListener("click", async () => {
  const ids = [...document.querySelectorAll("#platforms input:checked")].map(i => i.value);
  const jobs = await api("/api/jobs", {cv_text: $("#cv").value, conditions: $("#conditions").value, platform_ids: ids});
  if (jobs.error) { errorCard($("#jobs"), jobs.error); return; }
  $("#jobs").classList.remove("hidden");
  $("#jobs").innerHTML = `<h3>${jobs.length} matching offers</h3>` + jobs.slice(0, 25).map(j =>
    `<div class="job"><b>${Number(j.score)||0}%</b> <a href="${esc(j.url)}" target="_blank" rel="noopener noreferrer">${esc(j.title)}</a>
     — ${esc(j.company)} · ${esc(j.location)} <small>(${esc(j.source)})</small>
     <button class="use-offer" data-desc="${encodeURIComponent(j.description||"")}">Analyze this</button></div>`).join("");
  document.querySelectorAll(".use-offer").forEach(b => b.addEventListener("click", () => {
    $("#offer").value = decodeURIComponent(b.dataset.desc); $("#analyze").click();
  }));
});

$("#regen").addEventListener("click", async () => {
  const btn = $("#regen"); btn.disabled = true; btn.textContent = "Regenerating (loop)…";
  try {
    const out = await api("/api/regenerate", {cv: srcFrom($("#cv").value), offer: srcFrom($("#offer").value),
      aggressiveness: Number($("#agg").value)});
    if (out.error || !out.resume) { errorCard($("#regen-out"), out.error || "Regeneration failed"); return; }
    lastResume = out.resume;
    const ledger = (out.ledger && out.ledger.length)
      ? `<div class="ledger"><b>⚠ Verify before sending (added claims):</b><ul>${out.ledger.map(l=>`<li>${esc(l.claim)} — ${esc(l.why)}</li>`).join("")}</ul></div>`
      : `<p class="ok">No unverified claims added.</p>`;
    $("#regen-out").classList.remove("hidden");
    $("#regen-out").innerHTML = `<h3>Regenerated CV — Critic ${Number(out.critic_score)||0}/100 (${out.iterations} pass${out.iterations>1?"es":""}, ${out.passed?"passed":"best effort"})</h3>
      <button id="dl-pdf" class="primary">⬇ Download PDF</button>
      ${ledger}<pre>${esc(JSON.stringify(out.resume, null, 2))}</pre>`;
    $("#dl-pdf").addEventListener("click", downloadPdf);
  } finally { btn.disabled = false; btn.textContent = "Regenerate CV for this offer"; }
});

async function downloadPdf() {
  if (!lastResume) return;
  const btn = $("#dl-pdf"); btn.disabled = true; btn.textContent = "Rendering…";
  try {
    const resp = await fetch("/api/pdf", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({resume: lastResume})});
    if (!resp.ok) { const j = await resp.json().catch(()=>({})); alert("PDF export failed: " + (j.error||resp.status)); return; }
    const blob = await resp.blob();
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = "gradian-match-cv.pdf"; document.body.appendChild(a); a.click();
    a.remove(); URL.revokeObjectURL(a.href);
  } finally { btn.disabled = false; btn.textContent = "⬇ Download PDF"; }
}
boot();
