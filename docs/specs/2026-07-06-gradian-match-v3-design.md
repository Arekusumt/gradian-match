# Gradian Match v3 — Design & Self-Execution Spec

> Date: 2026-07-06 · Author: Gradian (agentic build) · Status: approved scope, executing.
> This document is BOTH the design spec and the **self-execution prompt**. The build follows it
> literally; isolated backend modules are handed to subagents against the API contracts below.

---

## 0. EXECUTION PROMPT (read this first, obey it throughout)

You are extending **Gradian Match** — a local, agentic CV ↔ job-offer tool. Ship, in one coordinated
effort, four confirmed workstreams and four accepted extras, then update GitHub. Work **test-first**
(the repo has a green pytest suite — keep it green, add tests for every new module), keep the
**deterministic core / agentic layer** split, route **all AI through `ai_client`**, preserve the
**truth-ledger + Critic ≥ 85 gate**, keep everything **local & private** (127.0.0.1, nothing leaves
the machine except the user's own AI calls and the job boards they enable), and keep the UI
**buildless vanilla JS**. Public-facing copy (README/landing) passes the CRO gate (`closer-cro` ≥ 80).
After each phase: run `pytest`, then the app boot smoke-check. Definition of done = all features live,
tests green, docs refreshed, pushed to `origin/main`.

**Hard rules (do not violate):**
1. No new heavyweight deps unless unavoidable; prefer stdlib + what's already in `requirements.txt`.
2. Never fabricate résumé claims silently — anything not grounded in the user's input goes in the ledger.
3. Persistence is **opt-in and local-only**, default **OFF**; the "nothing is stored" promise holds until the user turns it on, and there is a one-click wipe.
4. Subagents building isolated modules **must not edit `server.py` or `web/*`** — the orchestrator wires those to avoid conflicts.
5. Every new endpoint has a contract test; every new agent module has a unit test with a fake AI client.

---

## 1. Scope (approved 2026-07-06)

**Core (already requested):**
- **A. CV Builder from scratch** — put in your info → get the best possible, grounded, ATS-safe CV.
- **B. Job Finder** — more precise + more options: more free sources + real Jooble, filters, AI semantic re-rank + cross-source dedup.
- **C. Dashboard redesign** — neo-brutalist dashboard (sidebar + KPI cards + views).

**Accepted extras (all four):**
- **D. Cover-letter generator** (Tailor↔Critic loop + ledger).
- **E. Editable CV form + extra PDF templates** (ATS-safe, single-column).
- **F. Interview & gap-closing prep** (from the analysis).
- **G. Multi-offer fit ranking** (score one CV against many offers).

**Enabling change:**
- **H. Opt-in local library** (CVs / offers / runs) powering dashboard history + KPIs.

---

## 2. Invariants to preserve

- Dual AI backend (Claude Code CLI **or** Anthropic API) via `ai_client` — one door.
- Deterministic core (extract, taxonomy, scoring, verify, platform adapters) with **no AI**.
- Agentic layer = prompt modules in `src/gradianmatch/agents/*.md`, orchestrated by small Python drivers.
- Live **SSE agent console** for long runs (`events.py` + `/…/stream` routes).
- Truth-ledger everywhere the AI can add claims; Critic hard-gate on ungrounded claims.
- ATS-safe single-column PDF via Chrome/Edge headless (`render_pdf`).
- Local only; origin guard; in-memory by default.
- Buildless UI (`web/` vanilla JS), theme-aware (light/dark).

---

## 3. Data model & persistence

### 3.1 Résumé model (`resume_model.py`)
JSON Resume stays the canonical shape. **Add** optional `awards` and `volunteer` are out of scope
(YAGNI). No breaking changes; `resume_from_dict` already tolerates unknown keys.

### 3.2 Local library (`store.py`, NEW) — opt-in, local-only
- Root: `~/.gradian-match/` (user home, outside the repo). Never versioned.
- State file `~/.gradian-match/config.json`: `{"enabled": false}` (default OFF).
- Items: `~/.gradian-match/library/<id>.json` where each item is
  `{"id": str, "kind": "cv"|"offer"|"letter", "name": str, "created_at": iso8601, "data": {...}}`.
- Runs log `~/.gradian-match/runs.jsonl`: append-only `{"ts", "kind": "analyze"|"regenerate"|"build"|"letter"|"jobs"|"rank", "score": int|null, "label": str}` — powers KPIs. Only written when enabled.
- API:
  - `enabled() -> bool`, `set_enabled(bool)`
  - `save_item(kind, name, data) -> item` (raises if disabled)
  - `list_items(kind=None) -> [item]`, `get_item(id)`, `delete_item(id)`
  - `log_run(kind, score, label)` (no-op if disabled)
  - `overview() -> {"enabled", "runs_total", "best_score", "counts": {"cv","offer","letter"}, "recent": [last 8 runs]}`
  - `wipe()` — delete every file under root, reset config.
- Concurrency: single-user localhost; use a small file lock (`tempfile`/`os.replace` atomic writes). Good enough.

---

## 4. New agents (prompt modules)

All follow the house style: terse role, explicit inputs via `<<<TOKENS>>>`, **return ONLY JSON**,
mandatory ledger for anything not grounded.

- **`agents/architect.md`** — CV Builder.
  Inputs: `<<<INFO>>>` (freeform brain-dump), `<<<TARGET_ROLE>>>`, `<<<LANGUAGES>>>`, `<<<LINKS>>>`, `<<<FEEDBACK>>>`.
  Output: `{"resume": <JSON Resume>, "ledger": [ {claim, location, why, grounded:false} ]}`.
  Rules: structure and optimize (strong verbs, quantify where the user gave numbers, ATS section names),
  **never invent** employers/dates/degrees; anything inferred (e.g. a normalized job title) → ledger.
  Output language = language of `<<<INFO>>>` unless `<<<TARGET_ROLE>>>` implies otherwise.
- **`agents/letter_writer.md`** — Cover letter.
  Inputs: `<<<CV>>>` (JSON), `<<<OFFER>>>` (reqs JSON), `<<<TONE>>>` (warm|neutral|formal), `<<<FEEDBACK>>>`.
  Output: `{"letter": str (3–4 short paragraphs, one clear ask, no clichés), "ledger":[…]}`. Grounded in CV.
- **`agents/coach.md`** — Interview & gap prep.
  Inputs: `<<<CV>>>`, `<<<OFFER>>>`, `<<<REPORT>>>` (the compatibility report JSON).
  Output: `{"gap_plan":[{gap, how_to_close, effort:"quick|medium|deep"}], "questions":[{q, why, suggested_answer}]}`.

Critic gates reuse `agents/critic.md` conceptually; add **`rubrics/builder.yaml`** and **`rubrics/letter.yaml`**
(target 85; weights tuned per artifact). Builder/letter drivers run a bounded Writer↔Critic loop (max 2–3).

---

## 5. Backend modules & API contracts

New drivers under `src/gradianmatch/applier/` (isolated files → subagent-friendly). Each returns a
dataclass; the server serializes. **All request/response shapes are frozen here.**

### 5.1 CV Builder — `applier/builder.py`
`build_cv(info, target_role, languages: list[str], links: list[str], claude, rubric_path=None, emit=noop) -> BuildResult`
where `BuildResult{resume: Resume, ledger: [LedgerItem], critic_score:int, iterations:int, passed:bool}`.
- Route `POST /api/build` → body `{info:str, target_role:str="", languages:[str]=[], links:[str]=[]}` → `{resume, ledger, critic_score, iterations, passed}`.
- Route `POST /api/build/stream` → SSE console: Architect → Critic (loop).

### 5.2 Cover letter — `applier/cover_letter.py`
`write_letter(cv: Resume, offer: OfferReqs, tone:str, claude, emit=noop) -> LetterResult{letter:str, ledger, critic_score, passed}`.
- Route `POST /api/cover-letter` → `{cv:Source, offer:Source, tone:str="warm"}` → `{letter, ledger, critic_score, passed}`.
- Route `POST /api/cover-letter/stream` → SSE (analyst extracts offer → writer → critic).
- Letter PDF via existing `/api/pdf`? No — add `POST /api/letter-pdf` `{letter:str, name:str=""}` → PDF using `data/letter_template.html.j2`.

### 5.3 Interview & gap prep — `applier/interview.py`
`prep(cv: Resume, offer: OfferReqs, report: CompatibilityReport, claude) -> PrepResult{gap_plan:[…], questions:[…]}`.
- Route `POST /api/interview` → `{cv:Source, offer:Source}` → `{gap_plan, questions}` (runs analyze internally to get the report).

### 5.4 Multi-offer ranking — `applier/offer_rank.py`
`rank_offers(cv_text:str, offers:[{id,title,text}], claude, tax) -> [ {id, title, score, matched, missing} ]` (sorted desc).
- Route `POST /api/offers/rank` → `{cv_text:str, offers:[{id?:str, title?:str, text:str}]}` → the list.

### 5.5 Job Finder upgrade — `platforms.py` + `applier/jobs_search.py`
See §6.

### 5.6 PDF templates — `render_pdf.py` + `data/`
`render_pdf(resume, out_path, template:str="ats")`. Templates: `cv_template.html.j2` (rename-compatible alias `ats`),
`cv_template_modern.html.j2`, `cv_template_compact.html.j2` — all single-column, ATS-safe, bundled fonts.
- Route `POST /api/pdf` gains optional `template` field (default `ats`); `GET /api/templates` → `[{id,label,note}]`.

### 5.7 Library — `store.py`
- `GET /api/library` → `{enabled, items:[…]}` · `POST /api/library/enable`/`disable` → `{enabled}`
- `POST /api/library/save` → `{kind, name, data}` → item (400 if disabled)
- `GET /api/library/{id}` · `DELETE /api/library/{id}` · `POST /api/library/wipe`
- `GET /api/overview` → the KPI payload from `store.overview()`.
- Drivers call `store.log_run(...)` after analyze/regenerate/build/letter/jobs/rank (no-op if disabled).

---

## 6. Job Finder — precision + options

### 6.1 More sources (`platforms.py`)
Add adapters (all **free, no key** unless noted):
- `remoteok` — `https://remoteok.com/api` (first element is metadata; skip it; UA required).
- `jobicy` — `https://jobicy.com/api/v2/remote-jobs?count=50&tag=<q>` .
- `himalayas` — `https://himalayas.app/jobs/api?limit=50&search=<q>` .
- `jooble` — real POST `https://jooble.org/api/<key>` `{keywords, location}` (needs `JOOBLE_KEY`; skip if absent).
- `adzuna` — add **country selector** (`cfg`/req `country`, default `gb`→ make it `es` configurable), keep key-gated.
Registry `Platform.kind` stays `api|paste|xray|local`. Update `list_platforms` note text.

### 6.2 Filters (`jobs_search.py` + `JobsReq`)
`JobsReq` gains: `remote_only:bool=False`, `min_salary:int=0`, `max_age_days:int=0`, `job_type:str=""` (full-time/part-time/contract/internship), `country:str=""`.
- Apply deterministic post-filters over `JobPosting` (extend `JobPosting` with optional `remote:bool|None`, `posted_at:str`, `job_type:str`). Adapters fill what they expose.
- Salary parsing is best-effort (regex over `salary`/description); when unknown, don't exclude unless `min_salary>0` AND a number is found below it.

### 6.3 Cross-source dedup + AI semantic re-rank
- **Dedup**: key = normalized `(title.lower().strip(), company.lower().strip())`; keep the richest description; merge sources.
- **Re-rank**: keep the cheap keyword `_relevance` as a prefilter, then for the top N (≤ 25) call the AI once with a compact batch prompt (`agents/job_ranker.md`, NEW) → returns `[{index, score, reason}]`; blend `final = round(0.5*keyword + 0.5*ai)`. If AI unavailable, fall back to keyword only. One AI call per search (batched), not per posting.
- `RankedJob` gains optional `reason:str` for the UI.

---

## 7. Frontend — neo-brutalist dashboard

**Structure (`web/index.html`):** left **sidebar** nav + top bar (brand, backend status chip, theme, library switch).
Views (client-side router in `app.js`, hash-based, no framework):
1. **Overview / Home** — KPI cards (runs, best match, saved CVs/offers, backend), recent activity list (from `/api/overview`), quick actions. If library OFF, show a friendly "turn on local history" card instead of empty KPIs.
2. **Build** — CV builder: freeform brain-dump + guided fields (target role, languages, links) → agent console → editable CV form → PDF preview + template picker + "save to library".
3. **Match** — the existing analyze + regenerate (slider, ledger, PDF), reorganized as a view.
4. **Jobs** — Job Finder with the new filters (remote, salary, date, type, country) + source checkboxes; result cards show score + AI reason; "Analyze" / "Tailor for this" actions.
5. **Letter** — cover-letter generator (uses current CV/offer or library picks) → console → letter + ledger + PDF.
6. **Prep** — interview & gap prep view.
7. **Offers** — multi-offer ranking (paste/add several offers, or pull from library) → ranked list.
8. **Recruiter** — existing recruiter tools, reorganized.
9. **Library** — list saved CVs/offers/letters, open/delete, wipe, enable/disable toggle.

**Design system (`styles.css`):** keep the bold identity — thick borders, hard shadows, strong type,
brand gradient (teal `#2DD4BF` → indigo `#6366F1`) — but restructure into a **dashboard grid**: fixed
sidebar (collapsible on mobile), content area with KPI **stat cards**, **widget panels**, and a
consistent card/section rhythm. Preserve the signature **agent console** element and PDF preview.
Theme-aware light/dark retained. No horizontal body scroll; wide tables/console scroll internally.

**State (`app.js`):** a tiny store holding `currentCV`, `currentOffer`, `lastResume`, `libraryEnabled`.
Router renders views lazily. Reuse `streamRun`/`makeConsole`. Keep XSS escaping (`esc`).

---

## 8. Testing

- Unit tests per new driver with a **FakeClaude** returning canned JSON (pattern already in tests):
  `test_builder.py`, `test_cover_letter.py`, `test_interview.py`, `test_offer_rank.py`, `test_store.py`,
  `test_job_ranker.py`, plus extend `test_platforms.py` (new adapters, parsing) and `test_jobs_search.py` (filters, dedup, blended rank).
- Server contract tests extend `test_server.py`: every new route returns the frozen shape; disabled-library save → 400; template param respected; origin guard still applies.
- `store.py` tests use a temp `HOME` (monkeypatch) so nothing touches the real user dir.
- Keep the full suite green; target adding ~40–60 tests. Then run the stack **evals are in `vertex`, not here** — here we rely on pytest + boot smoke.

---

## 9. Execution phases (+ subagent map)

- **P0 — Spec + baseline** (orchestrator): this doc; confirm 98 tests green. ✅
- **P1 — Contracts & scaffolding** (orchestrator): add `store.py` skeleton, new agent prompt files, rubrics, `JobPosting`/`RankedJob`/`JobsReq` field additions, `resume`/template plumbing signatures — so parallel work aligns. Commit.
- **P2 — Isolated backend modules** (parallel subagents, tests included, **no server/web edits**):
  - S1: `builder.py` + `architect.md` + `rubrics/builder.yaml` + `test_builder.py`.
  - S2: `cover_letter.py` + `letter_writer.md` + `rubrics/letter.yaml` + `data/letter_template.html.j2` + `test_cover_letter.py`.
  - S3: `interview.py` + `coach.md` + `test_interview.py`.
  - S4: `offer_rank.py` + `test_offer_rank.py`.
  - S5: job sources + filters + dedup + `job_ranker.md` + rerank in `platforms.py`/`jobs_search.py` + tests.
  - S6: `store.py` full + `test_store.py`; PDF templates (`render_pdf` template arg + 2 templates) + `test_render_pdf` extension.
- **P3 — Server wiring** (orchestrator only): all routes + streams + `log_run` hooks + `test_server.py`. Run pytest.
- **P4 — Dashboard** (orchestrator, optionally one `web-designer`/`frontend` subagent working ONLY in `web/`): full redesign, iterate with Playwright screenshots.
- **P5 — QA** (orchestrator + `qa-auditor`): pytest, boot smoke, Lighthouse/a11y on the UI, `closer-cro` on README/landing copy.
- **P6 — Docs + push** (orchestrator): README v3, refresh `docs/how-it-works` + `docs/system-map`, `.env.example` (new keys/notes), commit in logical chunks, push to `origin/main`.

## 10. Definition of Done
1. Build, Cover letter, Interview prep, Multi-offer rank, editable CV + templates, upgraded Job Finder, opt-in library, and the dashboard are all live and wired.
2. `python -m pytest` green (baseline 98 + new).
3. App boots via `start.bat`; every view works against a connected AI (smoke-checked).
4. README + docs + `.env.example` updated; public copy ≥ CRO 80.
5. Pushed to `github.com/Arekusumt/gradian-match` `main`.
