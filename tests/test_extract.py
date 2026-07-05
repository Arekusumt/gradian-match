from pathlib import Path
from gradianmatch.extract import extract_text, ExtractResult

FIX = Path(__file__).parent / "fixtures"

def test_plaintext_passthrough():
    r = extract_text("hello world", "text")
    assert isinstance(r, ExtractResult)
    assert r.text == "hello world" and r.warnings == []

def test_pdf_extracts_text_and_meta():
    r = extract_text(str(FIX / "sample_cv.pdf"), "pdf")
    assert "Python" in r.text
    assert "producer" in r.meta  # may be "" but key present, used later by AI-signals

def test_pdf_empty_warns_scanned():
    from gradianmatch.extract import _scanned_warning
    assert "scanned" in _scanned_warning().lower()

def test_url_uses_injected_fetcher():
    html = "<html><body><h1>Job</h1><p>SQL and Python</p><script>x</script></body></html>"
    r = extract_text("http://example.com", "url", fetcher=lambda u: html)
    assert "Python" in r.text and "<script>" not in r.text
