# src/gradianmatch/recruiter/ai_signals.py
"""Heuristic (+ optional agentic) signals that a CV was AI-written.

SIGNALS, NOT PROOF. Everything here is deterministic and computed regardless of
``claude``; when a claude client is provided, the Examiner agent's verdict is
blended in by taking the HIGHER of the two bands. Never auto-reject on this.
"""
from __future__ import annotations
import re
import statistics
from dataclasses import dataclass
from gradianmatch import config

DISCLAIMER = (
    "These are signals, not proof. Do not auto-reject a candidate on this "
    "basis; verify with an interview and the source checks."
)

# Curated AI-tell filler phrases (lowercased). Matched as substrings.
AI_TELLS = [
    "results-driven", "proven track record", "leverage synergies",
    "dynamic professional", "passionate about", "detail-oriented team player",
    "responsible for a wide range", "in today's fast-paced", "spearheaded",
    "utilize", "wide array of",
]

# Markers in PDF producer/creator that suggest an AI or template CV builder.
AI_DOC_MARKERS = [
    "gpt", "openai", "chatgpt", "claude", "anthropic", "gemini", "copilot",
    "llama", "mistral", "jasper", "writesonic", "notion ai",
    "resume.io", "novoresume", "zety", "kickresume", "canva", "enhancv",
]

# Weights for combining the four sub-scores (generic + specifics are the strong
# ones; uniformity + pdf are mild).
_W_GENERIC, _W_SPECIFICS, _W_UNIFORMITY, _W_PDF = 0.45, 0.35, 0.12, 0.08

_BAND_ORDER = {"Low": 0, "Medium": 1, "High": 2}
_BAND_FLOOR = {"Low": 0, "Medium": 34, "High": 67}


@dataclass
class AiSignalReport:
    band: str
    score_0_100: int
    evidence: list[str]
    heuristics: dict
    disclaimer: str


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]


def _band(score: int) -> str:
    if score > 66:
        return "High"
    if score >= 34:
        return "Medium"
    return "Low"


def _generic(text: str) -> tuple[int, float, int]:
    low = text.lower()
    n_words = max(1, len(_words(text)))
    hits = sum(low.count(p) for p in AI_TELLS)
    density = hits / n_words * 100  # per 100 words
    score = int(min(100, round(density * 22)))
    return score, density, hits


def _specifics(sentences: list[str]) -> tuple[int, float]:
    if not sentences:
        return 0, 0.0
    with_spec = sum(1 for s in sentences if re.search(r"[\d%]", s))
    ratio = with_spec / len(sentences)
    score = int(round((1.0 - ratio) * 100))  # LOW specifics => high AI signal
    return score, ratio


def _uniformity(sentences: list[str]) -> tuple[int, float]:
    counts = [len(_words(s)) for s in sentences]
    if len(counts) < 2:
        return 0, 1.0
    mean = statistics.mean(counts) or 1
    cov = statistics.pstdev(counts) / mean  # coefficient of variation
    score = int(round(max(0.0, min(1.0, 1.0 - min(cov, 1.0))) * 100))
    return score, cov


def _pdf(pdf_meta: dict | None) -> tuple[int, str]:
    if not pdf_meta:
        return 50, "No PDF metadata available (producer/creator empty)."
    blob = (str(pdf_meta.get("producer", "")) + " "
            + str(pdf_meta.get("creator", ""))).strip().lower()
    if not blob:
        return 50, "PDF producer/creator fields are empty."
    for m in AI_DOC_MARKERS:
        if m in blob:
            return 90, f"PDF tool marker suggests AI/template builder: '{m}'."
    return 10, f"PDF produced by a conventional tool ({blob[:40]})."


def _qual(value: float, hi: float, mid: float) -> str:
    return "high" if value >= hi else ("moderate" if value >= mid else "low")


def _fill_examiner(cv_text: str) -> str:
    tmpl = (config.AGENTS_DIR / "examiner.md").read_text(encoding="utf-8")
    return tmpl.replace("<<<CV>>>", cv_text)


def ai_signals(cv_text: str, pdf_meta: dict | None, claude=None) -> AiSignalReport:
    cv_text = cv_text or ""
    sentences = _sentences(cv_text)

    generic_score, density, hits = _generic(cv_text)
    specifics_score, spec_ratio = _specifics(sentences)
    uniformity_score, cov = _uniformity(sentences)
    pdf_score, pdf_note = _pdf(pdf_meta)

    score = int(round(
        _W_GENERIC * generic_score + _W_SPECIFICS * specifics_score
        + _W_UNIFORMITY * uniformity_score + _W_PDF * pdf_score))
    score = max(0, min(100, score))
    band = _band(score)

    evidence = [
        f"Generic-phrase density {_qual(density, 3.0, 1.2)}: "
        f"{density:.1f} per 100 words ({hits} AI-tell phrase(s)).",
        f"Specifics density {_qual((1 - spec_ratio) * 100, 66, 34)}: "
        f"{spec_ratio * 100:.0f}% of sentences cite a number or percentage.",
        f"Sentence-length uniformity {_qual(uniformity_score, 66, 40)} "
        f"(coefficient of variation {cov:.2f}).",
        pdf_note,
    ]

    heuristics = {
        "generic_phrase_density_per_100w": round(density, 2),
        "generic_score": generic_score,
        "specifics_ratio": round(spec_ratio, 2),
        "specifics_score": specifics_score,
        "sentence_length_cov": round(cov, 2),
        "uniformity_score": uniformity_score,
        "pdf_score": pdf_score,
        "combined": score,
    }

    if claude is not None:
        try:
            raw = claude.run_json(_fill_examiner(cv_text))
        except Exception:  # noqa: BLE001 — examiner failure must not break signals
            raw = None
        if isinstance(raw, dict):
            likelihood = str(raw.get("ai_likelihood", "")).strip().lower()
            ex_band = {"low": "Low", "medium": "Medium", "high": "High"}.get(likelihood)
            if ex_band:
                heuristics["examiner_band"] = ex_band
                evidence.append(f"Examiner (AI) assessed AI-likelihood: {likelihood}.")
                if _BAND_ORDER[ex_band] > _BAND_ORDER[band]:
                    band = ex_band
                    score = max(score, _BAND_FLOOR[ex_band])
                    heuristics["combined"] = score
            for e in (raw.get("evidence") or []):
                if isinstance(e, str) and e.strip():
                    evidence.append(f"Examiner: {e.strip()}")

    return AiSignalReport(band=band, score_0_100=score, evidence=evidence,
                          heuristics=heuristics, disclaimer=DISCLAIMER)
