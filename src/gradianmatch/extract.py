# src/gradianmatch/extract.py
from __future__ import annotations
import html
import re
from dataclasses import dataclass, field
from typing import Callable
import httpx
import pdfplumber

@dataclass
class ExtractResult:
    text: str
    warnings: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

def _scanned_warning() -> str:
    return "This PDF has no selectable text (likely scanned). Paste the text instead."

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_STRIP = re.compile(r"<[^>]+>")
_WS = re.compile(r"\n{3,}")

def _html_to_text(markup: str) -> str:
    markup = _TAG.sub(" ", markup)
    text = _STRIP.sub("\n", markup)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return _WS.sub("\n\n", text).strip()

def extract_plaintext(s: str) -> ExtractResult:
    return ExtractResult(text=s.strip())

def extract_pdf(path: str) -> ExtractResult:
    warnings, parts, meta = [], [], {}
    with pdfplumber.open(path) as pdf:
        raw = pdf.metadata or {}
        meta = {"producer": raw.get("Producer", ""), "creator": raw.get("Creator", ""),
                "pages": len(pdf.pages)}
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    text = "\n".join(parts).strip()
    if not text:
        warnings.append(_scanned_warning())
    return ExtractResult(text=text, warnings=warnings, meta=meta)

def extract_url(url: str, fetcher: Callable[[str], str] | None = None) -> ExtractResult:
    if fetcher is None:
        def fetcher(u: str) -> str:
            resp = httpx.get(u, follow_redirects=True, timeout=20,
                             headers={"User-Agent": "GradianMatch/0.1"})
            resp.raise_for_status()
            return resp.text
    page = fetcher(url)
    return ExtractResult(text=_html_to_text(page), meta={"source_url": url})

def extract_text(source: str, kind: str, fetcher: Callable[[str], str] | None = None) -> ExtractResult:
    if kind == "text":
        return extract_plaintext(source)
    if kind == "pdf":
        return extract_pdf(source)
    if kind == "url":
        return extract_url(source, fetcher=fetcher)
    raise ValueError(f"unknown kind: {kind}")
