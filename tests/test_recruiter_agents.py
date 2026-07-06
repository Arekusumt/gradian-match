from gradianmatch import config


def _read(name: str) -> str:
    return (config.AGENTS_DIR / name).read_text(encoding="utf-8")


def test_examiner_prompt_contract():
    t = _read("examiner.md")
    assert "<<<CV>>>" in t
    assert "Return ONLY" in t
    for key in ("ai_likelihood", "evidence", "notes"):
        assert key in t
    assert "low|medium|high" in t


def test_sourcer_prompt_contract():
    t = _read("sourcer.md")
    assert "<<<OFFER>>>" in t
    assert "Return ONLY" in t
    for key in ("github", "language", "location", "keywords", "xray"):
        assert key in t
