import shutil, pytest
from gradianmatch.resume_model import resume_from_dict
from gradianmatch.render_pdf import render_html, render_pdf, find_chrome

R = resume_from_dict({"basics": {"name": "Sam Rivera", "email": "a@x.com"},
                      "work": [{"name": "Gradian", "position": "Analyst",
                                "highlights": ["Built an engine"]}],
                      "skills": [{"name": "Prog", "keywords": ["Python", "SQL"]}]})

def test_render_html_contains_content():
    html = render_html(R)
    assert "Sam Rivera" in html and "Python" in html and "<h1" in html

def test_render_pdf_smoke(tmp_path):
    if find_chrome() is None:
        pytest.skip("Chrome not installed in this environment")
    out = tmp_path / "cv.pdf"
    render_pdf(R, str(out))
    assert out.exists() and out.stat().st_size > 800

def test_render_html_escapes_special_chars():
    r = resume_from_dict({"basics": {"name": "R&D <lead>", "summary": "C++ & SQL"}})
    html = render_html(r)
    assert "R&amp;D" in html and "&lt;lead&gt;" in html and "C++ &amp; SQL" in html
