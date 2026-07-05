from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from gradianmatch import config
from gradianmatch.resume_model import Resume, resume_from_dict, resume_to_dict
from gradianmatch.scoring import OfferReqs

DEFAULT_RUBRIC = {"target_score": 85, "max_iterations": 3}

def _as_int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

@dataclass
class LedgerItem:
    claim: str; location: str; why: str; grounded: bool = False

@dataclass
class RegenResult:
    resume: Resume
    ledger: list[LedgerItem]
    critic_score: int
    iterations: int
    passed: bool
    feedback: list[str] = field(default_factory=list)

def _rubric(path):
    if path is None:
        p = config.RUBRICS_DIR / "critic.yaml"
        if not p.exists():
            return DEFAULT_RUBRIC
        path = p
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def _fill(template_name, **kw) -> str:
    t = (config.AGENTS_DIR / template_name).read_text(encoding="utf-8")
    if not kw:
        return t
    pattern = re.compile("|".join(re.escape(k) for k in kw))
    return pattern.sub(lambda m: kw[m.group(0)], t)

def _offer_json(offer: OfferReqs) -> str:
    return json.dumps(offer.__dict__, ensure_ascii=False)

def regenerate(cv: Resume, offer: OfferReqs, aggressiveness: int, claude,
               rubric_path=None) -> RegenResult:
    rub = _rubric(rubric_path)
    target, max_iter = rub.get("target_score", 85), rub.get("max_iterations", 3)
    cv_json = json.dumps(resume_to_dict(cv), ensure_ascii=False)
    feedback: list[str] = []
    best = None
    for i in range(1, max_iter + 1):
        tprompt = _fill("tailor.md", **{"<<<CV>>>": cv_json, "<<<OFFER>>>": _offer_json(offer),
                        "<<<AGG>>>": str(aggressiveness),
                        "<<<FEEDBACK>>>": json.dumps(feedback, ensure_ascii=False)})
        tout = claude.run_json(tprompt)
        if not isinstance(tout, dict):
            tout = {}
        tailored = resume_from_dict(tout.get("resume") or {})
        ledger = []
        for item in (tout.get("ledger") or []):
            if isinstance(item, dict):
                ledger.append(LedgerItem(
                    claim=str(item.get("claim", "")), location=str(item.get("location", "")),
                    why=str(item.get("why", "")), grounded=bool(item.get("grounded", False))))

        cprompt = _fill("critic.md", **{"<<<RUBRIC>>>": json.dumps(rub), "<<<OFFER>>>": _offer_json(offer),
                        "<<<CV>>>": cv_json, "<<<TAILORED>>>": json.dumps(resume_to_dict(tailored), ensure_ascii=False),
                        "<<<LEDGER>>>": json.dumps([l.__dict__ for l in ledger], ensure_ascii=False)})
        cout = claude.run_json(cprompt)
        if not isinstance(cout, dict):
            cout = {}
        score = _as_int(cout.get("score", 0))
        passed = bool(cout.get("passed", False)) and not cout.get("hard_gate_violations")
        feedback = list(cout.get("feedback") or []) + list(cout.get("hard_gate_violations") or [])

        candidate = RegenResult(tailored, ledger, score, i, passed, feedback)
        if best is None or score >= best.critic_score:
            best = candidate
        if passed and score >= target:
            return candidate
    return best
