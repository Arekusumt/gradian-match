const $ = (s) => document.querySelector(s);
const api = (path, body) => fetch(path, {method: body ? "POST" : "GET",
  headers: {"Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined})
  .then(r => r.json());

function srcFrom(text) {
  const t = text.trim();
  return /^https?:\/\//i.test(t) ? {kind: "url", value: t} : {kind: "text", value: t};
}

async function boot() {
  const h = await api("/api/health");
  const s = $("#claude-status");
  s.textContent = h.claude_ok ? "Claude Code ✓" : "Claude Code ✗";
  s.className = "status " + (h.claude_ok ? "ok" : "bad");
  if (!h.claude_ok) s.title = h.message;
  const plats = await api("/api/platforms?side=applier");
  $("#platforms").innerHTML = plats.filter(p => p.kind === "api")
    .map(p => `<label><input type="checkbox" value="${p.id}" ${["arbeitnow","remotive"].includes(p.id)?"checked":""}>${p.label}</label>`).join(" ");
}

$("#agg").addEventListener("input", e => $("#agg-val").textContent = e.target.value);

document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  if (t.disabled) return;
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
}));

function catBar(c) {
  return `<div class="cat"><span>${c.name}</span><div class="bar"><i style="width:${c.score_0_100}%"></i></div>
    <b>${c.score_0_100}</b><small>${c.details||""}</small></div>`;
}

$("#analyze").addEventListener("click", async () => {
  const btn = $("#analyze"); btn.disabled = true; btn.textContent = "Analyzing…";
  try {
    const rep = await api("/api/analyze", {cv: srcFrom($("#cv").value), offer: srcFrom($("#offer").value)});
    $("#report").classList.remove("hidden");
    if (rep.error) {
      $("#report").innerHTML = `<p class="error">${rep.error}</p>`;
    } else {
      $("#report").innerHTML = `<h3>Compatibility: ${rep.overall}%</h3>
        ${rep.categories.map(catBar).join("")}
        <p><b>Matched:</b> ${rep.matched_keywords.join(", ")||"—"}</p>
        <p><b>Missing:</b> ${rep.missing_keywords.join(", ")||"—"}</p>
        <p><b>Do next:</b></p><ul>${rep.suggestions.map(s=>`<li>${s}</li>`).join("")}</ul>`;
    }
  } finally { btn.disabled = false; btn.textContent = "Analyze compatibility"; }
});

$("#find-jobs").addEventListener("click", async () => {
  const ids = [...document.querySelectorAll("#platforms input:checked")].map(i => i.value);
  const jobs = await api("/api/jobs", {cv_text: $("#cv").value, conditions: "", platform_ids: ids});
  $("#jobs").classList.remove("hidden");
  if (jobs.error) {
    $("#jobs").innerHTML = `<p class="error">${jobs.error}</p>`;
    return;
  }
  $("#jobs").innerHTML = `<h3>${jobs.length} matching offers</h3>` + jobs.slice(0, 25).map(j =>
    `<div class="job"><b>${j.score}%</b> <a href="${j.url}" target="_blank">${j.title}</a>
     — ${j.company} · ${j.location} <small>(${j.source})</small>
     <button class="use-offer" data-desc="${encodeURIComponent(j.description)}">Analyze this</button></div>`).join("");
  document.querySelectorAll(".use-offer").forEach(b => b.addEventListener("click", () => {
    $("#offer").value = decodeURIComponent(b.dataset.desc); $("#analyze").click();
  }));
});

$("#regen").addEventListener("click", async () => {
  const btn = $("#regen"); btn.disabled = true; btn.textContent = "Regenerating (loop)…";
  try {
    const out = await api("/api/regenerate", {cv: srcFrom($("#cv").value), offer: srcFrom($("#offer").value),
      aggressiveness: Number($("#agg").value)});
    $("#regen-out").classList.remove("hidden");
    if (out.error) {
      $("#regen-out").innerHTML = `<p class="error">${out.error}</p>`;
      return;
    }
    const ledger = out.ledger.length
      ? `<div class="ledger"><b>⚠ Verify before sending (added claims):</b><ul>${out.ledger.map(l=>`<li>${l.claim} — ${l.why}</li>`).join("")}</ul></div>`
      : `<p class="ok">No unverified claims added.</p>`;
    $("#regen-out").innerHTML = `<h3>Regenerated CV — Critic ${out.critic_score}/100 (${out.iterations} pass${out.iterations>1?"es":""}, ${out.passed?"passed":"best effort"})</h3>
      ${ledger}<pre>${JSON.stringify(out.resume, null, 2)}</pre>`;
  } finally { btn.disabled = false; btn.textContent = "Regenerate CV for this offer"; }
});
boot();
