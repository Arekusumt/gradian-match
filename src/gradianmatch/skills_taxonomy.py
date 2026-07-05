# src/gradianmatch/skills_taxonomy.py
from __future__ import annotations
import json
from pathlib import Path
from gradianmatch import config

def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())

class SkillTaxonomy:
    def __init__(self, path: Path | None = None):
        path = path or (config.DATA_DIR / "skills.json")
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self._canon: dict[str, str] = {}
        self._syn: dict[str, set[str]] = {}
        for canon, syns in raw.items():
            c = _norm(canon)
            variants = {c} | {_norm(x) for x in syns}
            self._syn[c] = variants
            for v in variants:
                self._canon[v] = c

    def normalize(self, s: str) -> str | None:
        return self._canon.get(_norm(s))

    def expand(self, s: str) -> set[str]:
        c = self.normalize(s)
        return set(self._syn.get(c, {_norm(s)}))

    def match(self, cv_terms: set[str], needle: str) -> bool:
        cv_norm = {_norm(t) for t in cv_terms}
        cv_canon = {self._canon.get(t, t) for t in cv_norm}
        target = self.normalize(needle) or _norm(needle)
        return target in cv_canon or bool(self.expand(needle) & cv_norm)
