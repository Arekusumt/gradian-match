# Gradian Match

A local, agentic CV ↔ job-offer analyzer by **[Gradian](https://gradiangrowth.com)**.
It runs entirely on your machine and on **your own Claude Code account** — no API keys to buy.

## Applier (v1)
- **Explainable compatibility score** — ATS keyword coverage + recruiter gating (languages, years) + Claude's semantic fit, each shown separately so you see *why*.
- **Job Finder** across free job boards (Arbeitnow, Remotive; add Adzuna/Jooble keys for more), or paste a specific offer link.
- **Regenerate your CV** for a specific offer with a 1–100 tailoring slider, refined by an internal **Tailor↔Critic loop**, plus a transparency **ledger** of anything newly claimed — and a one-click **PDF export**.

*Recruiter mode (screening candidates, AI-likelihood signals, source verification) is planned for v2.*

## Requirements
1. **Claude Code**, installed and signed in — https://claude.com/claude-code
   (check with `claude --version`). Gradian Match calls it under the hood; nothing works without it.
2. **Python 3.11+** and **Google Chrome or Microsoft Edge** (used to export the CV to PDF).

## Run (Windows)
1. Download or clone this repo.
2. Double-click **`start.bat`** — the first run creates a virtual environment and installs dependencies automatically.
3. Your browser opens at **http://127.0.0.1:8765**.

Paste (or upload a PDF of) your CV and the job offer, then **Analyze**. Move the slider and **Regenerate** to get a tailored CV you can download as a PDF.

## Optional job-board keys
The analyze/regenerate core needs **nothing** but Claude Code. For wider Job Finder coverage, copy `.env.example` to `.env` and add a free [Adzuna](https://developer.adzuna.com/) key.

## Privacy & safety
Everything runs locally. Nothing is stored; the only text that leaves your machine goes to *your* Claude Code account and any job boards you enable. The server binds to **127.0.0.1** (your machine only) and rejects cross-origin requests — **do not** expose it to a public network.

The tailoring slider can *emphasize* your real experience aggressively, but the transparency ledger flags anything it adds beyond your source CV. You are responsible for the accuracy of what you send to employers.

## License
© Gradian. All rights reserved. (Add an explicit license file before public distribution.)
