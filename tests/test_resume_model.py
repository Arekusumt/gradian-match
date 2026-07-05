from gradianmatch.resume_model import resume_from_dict, resume_to_dict, Resume

RAW = {
    "basics": {"name": "Alex", "email": "a@x.com", "summary": "Analyst",
               "profiles": [{"network": "GitHub", "url": "github.com/Arekusumt"}]},
    "work": [{"name": "Gradian", "position": "Founder", "startDate": "2025",
              "highlights": ["Built an agentic engine"]}],
    "skills": [{"name": "Programming", "keywords": ["Python", "SQL"]}],
    "languages": [{"language": "English", "fluency": "Fluent"}],
}

def test_roundtrip_preserves_known_fields():
    r = resume_from_dict(RAW)
    assert isinstance(r, Resume)
    assert r.basics.name == "Alex"
    assert r.work[0].highlights == ["Built an agentic engine"]
    assert r.skills[0].keywords == ["Python", "SQL"]
    back = resume_to_dict(r)
    assert back["basics"]["name"] == "Alex"
    assert back["work"][0]["position"] == "Founder"

def test_missing_sections_default_empty():
    r = resume_from_dict({"basics": {"name": "X"}})
    assert r.work == [] and r.skills == [] and r.education == []

def test_all_skill_keywords_collects_flat_set():
    r = resume_from_dict(RAW)
    assert r.all_skill_terms() >= {"python", "sql"}
