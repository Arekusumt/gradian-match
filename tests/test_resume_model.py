from gradianmatch.resume_model import resume_from_dict, resume_to_dict, Resume

RAW = {
    "basics": {"name": "Sam", "email": "a@x.com", "summary": "Analyst",
               "profiles": [{"network": "GitHub", "url": "github.com/sam-rivera-dev"}]},
    "work": [{"name": "Gradian", "position": "Founder", "startDate": "2025",
              "highlights": ["Built an agentic engine"]}],
    "skills": [{"name": "Programming", "keywords": ["Python", "SQL"]}],
    "languages": [{"language": "English", "fluency": "Fluent"}],
}

def test_roundtrip_preserves_known_fields():
    r = resume_from_dict(RAW)
    assert isinstance(r, Resume)
    assert r.basics.name == "Sam"
    assert r.work[0].highlights == ["Built an agentic engine"]
    assert r.skills[0].keywords == ["Python", "SQL"]
    back = resume_to_dict(r)
    assert back["basics"]["name"] == "Sam"
    assert back["work"][0]["position"] == "Founder"

def test_missing_sections_default_empty():
    r = resume_from_dict({"basics": {"name": "X"}})
    assert r.work == [] and r.skills == [] and r.education == []

def test_all_skill_keywords_collects_flat_set():
    r = resume_from_dict(RAW)
    assert r.all_skill_terms() >= {"python", "sql"}

def test_null_list_field_defaults_empty():
    r = resume_from_dict({"skills": [{"name": "P", "keywords": None}]})
    assert r.skills[0].keywords == []
    assert r.all_skill_terms() == {"p"}  # no crash

def test_non_dict_list_items_are_skipped():
    r = resume_from_dict({"work": ["garbage", None, {"position": "Analyst"}]})
    assert [w.position for w in r.work] == ["Analyst"]

def test_resume_from_dict_handles_non_dict():
    assert resume_from_dict(None).basics.name == ""
    assert resume_from_dict("garbage").work == []
