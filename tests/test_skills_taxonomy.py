import unicodedata

from gradianmatch.skills_taxonomy import SkillTaxonomy

def test_normalize_maps_synonym_to_canonical():
    t = SkillTaxonomy()
    assert t.normalize("PowerBI") == "power bi"
    assert t.normalize("postgres") == "sql"
    assert t.normalize("totally-unknown-skill") is None

def test_expand_includes_self_and_synonyms():
    t = SkillTaxonomy()
    exp = t.expand("power bi")
    assert "power bi" in exp and "pbi" in exp

def test_match_against_cv_terms_uses_synonyms():
    t = SkillTaxonomy()
    cv_terms = {"powerbi", "python"}
    assert t.match(cv_terms, "Power BI") is True
    assert t.match(cv_terms, "azure") is False

def test_normalize_handles_accents_and_unicode_forms():
    t = SkillTaxonomy()
    assert t.normalize("anàlisi de dades") == "data analysis"
    nfd = unicodedata.normalize("NFD", "anàlisi de dades")
    assert t.normalize(nfd) == "data analysis"  # NFD input still matches
