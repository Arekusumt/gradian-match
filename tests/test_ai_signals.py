from gradianmatch.recruiter.ai_signals import ai_signals, AiSignalReport

# A human-sounding CV: varied sentence lengths, lots of concrete specifics, no filler.
HUMAN_CV = (
    "In 2023 I migrated 4 Postgres databases to a new cluster, cutting query latency by 38%. "
    "I mentor two junior analysts every Friday. "
    "Last quarter our team shipped a churn model that flagged 1,200 at-risk accounts. "
    "My R script reconciles 17 Idescat tables into one panel. "
    "I also fixed a nasty timezone bug that had corrupted 3 months of logs."
)

# A bland, generic CV: many AI-tell phrases, uniform sentence rhythm, zero specifics.
GENERIC_CV = (
    "I am a results-driven dynamic professional passionate about data. "
    "I have a proven track record and utilize a wide array of tools. "
    "I am a detail-oriented team player in today's fast-paced world. "
    "I leverage synergies and spearheaded many cross functional teams. "
    "I am passionate about delivering value and utilize best practices."
)


def test_human_cv_scores_low():
    rep = ai_signals(HUMAN_CV, pdf_meta={"producer": "LaTeX with hyperref"})
    assert isinstance(rep, AiSignalReport)
    assert rep.band == "Low"
    assert rep.score_0_100 < 34
    assert rep.evidence  # human-readable bullets present
    assert "specifics" in " ".join(rep.evidence).lower() or rep.heuristics


def test_generic_cv_scores_higher():
    human = ai_signals(HUMAN_CV, pdf_meta={"producer": "LaTeX"})
    generic = ai_signals(GENERIC_CV, pdf_meta=None)
    assert generic.score_0_100 > human.score_0_100
    assert generic.band in ("Medium", "High")


def test_disclaimer_is_always_present():
    rep = ai_signals(GENERIC_CV, pdf_meta=None)
    assert rep.disclaimer == (
        "These are signals, not proof. Do not auto-reject a candidate on this "
        "basis; verify with an interview and the source checks."
    )


def test_works_without_claude():
    rep = ai_signals(HUMAN_CV, pdf_meta=None, claude=None)
    assert isinstance(rep, AiSignalReport)
    assert 0 <= rep.score_0_100 <= 100
    assert rep.band in ("Low", "Medium", "High")


class FakeExaminer:
    def __init__(self, likelihood, evidence=None):
        self.likelihood = likelihood
        self.evidence = evidence or []
        self.prompts = []

    def run_json(self, prompt, timeout=300):
        self.prompts.append(prompt)
        return {"ai_likelihood": self.likelihood, "evidence": self.evidence, "notes": ""}


def test_examiner_raises_the_band():
    fake = FakeExaminer("high", evidence=["Reads like a template."])
    rep = ai_signals(HUMAN_CV, pdf_meta={"producer": "LaTeX"}, claude=fake)
    assert rep.band == "High"  # examiner outranks the low heuristic band
    assert rep.score_0_100 >= 67
    assert any("template" in e.lower() for e in rep.evidence)  # examiner evidence merged
    assert "<<<CV>>>" not in fake.prompts[0]  # placeholder was filled


class BadExaminer:
    def run_json(self, prompt, timeout=300):
        return []  # malformed / non-dict output


class BoomExaminer:
    def run_json(self, prompt, timeout=300):
        raise RuntimeError("cli down")


def test_malformed_examiner_is_ignored():
    base = ai_signals(HUMAN_CV, pdf_meta={"producer": "LaTeX"})
    bad = ai_signals(HUMAN_CV, pdf_meta={"producer": "LaTeX"}, claude=BadExaminer())
    boom = ai_signals(HUMAN_CV, pdf_meta={"producer": "LaTeX"}, claude=BoomExaminer())
    assert bad.band == base.band == "Low"
    assert boom.band == "Low"  # exception swallowed, heuristics stand
