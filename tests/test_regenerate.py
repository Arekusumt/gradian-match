from gradianmatch.resume_model import resume_from_dict
from gradianmatch.scoring import OfferReqs
from gradianmatch.applier.regenerate import regenerate

CV = resume_from_dict({"basics": {"name": "Sam"},
                       "skills": [{"name": "p", "keywords": ["Python", "SQL"]}]})
OFFER = OfferReqs(title="Data Analyst", must_have_skills=["Python", "SQL", "Power BI"])

class ScriptedClaude:
    """Returns queued payloads in order; records prompts to know who was called."""
    def __init__(self, payloads): self.payloads = list(payloads); self.prompts = []
    def run_json(self, prompt, timeout=120):
        self.prompts.append(prompt)
        return self.payloads.pop(0)

TAILORED = {"resume": {"basics": {"name": "Sam"},
                       "skills": [{"name": "p", "keywords": ["Python", "SQL", "Power BI"]}]},
            "ledger": [{"claim": "Power BI", "location": "skills", "why": "added for match", "grounded": False}]}

def test_loop_stops_when_critic_passes():
    claude = ScriptedClaude([TAILORED, {"score": 88, "dimensions": {}, "passed": True,
                                        "hard_gate_violations": [], "feedback": []}])
    res = regenerate(CV, OFFER, 80, claude, rubric_path=None)
    assert res.critic_score == 88 and res.iterations == 1
    assert any(item.claim == "Power BI" for item in res.ledger)

def test_loop_retries_then_returns_best():
    claude = ScriptedClaude([
        TAILORED, {"score": 60, "dimensions": {}, "passed": False,
                   "hard_gate_violations": [], "feedback": ["Quantify impact"]},
        TAILORED, {"score": 90, "dimensions": {}, "passed": True,
                   "hard_gate_violations": [], "feedback": []},
    ])
    res = regenerate(CV, OFFER, 80, claude, rubric_path=None)
    assert res.iterations == 2 and res.critic_score == 90

def test_regenerate_survives_malformed_tailor():
    claude = ScriptedClaude(["not a dict",
                             {"score": 90, "passed": True, "hard_gate_violations": [], "feedback": []}])
    res = regenerate(CV, OFFER, 50, claude, rubric_path=None)
    assert res.iterations == 1 and res.critic_score == 90
    assert res.resume.basics.name == ""  # non-dict tailor → empty resume, no crash

def test_regenerate_coerces_nonnumeric_score():
    tailored = {"resume": {"basics": {"name": "A"}}, "ledger": []}
    critic = {"score": "high", "passed": False, "hard_gate_violations": [], "feedback": ["x"]}
    claude = ScriptedClaude([tailored, critic, tailored, critic, tailored, critic])
    res = regenerate(CV, OFFER, 50, claude, rubric_path=None)
    assert res.critic_score == 0 and res.iterations == 3  # coerced, ran to max, no crash
