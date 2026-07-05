import httpx
from fastapi.testclient import TestClient

from gradianmatch import server


class _FakeClaude:
    def run_json(self, prompt, timeout=120):
        return {"cv": {"basics": {"name": "Alex"}, "skills": [{"name": "p", "keywords": ["Python"]}]},
                "offer": {"title": "Analyst", "must_have_skills": ["Python", "Power BI"],
                          "nice_to_have_skills": [], "min_years": 0, "languages": [], "seniority": "junior",
                          "location": "", "remote": None, "education": ""},
                "semantic": {"score_0_100": 70, "rationale": "ok", "transferable": [], "red_flags": []}}

    def check_available(self):
        return True, "ok"


def make_client(monkeypatch):
    monkeypatch.setattr(server, "get_claude", lambda: _FakeClaude())
    return TestClient(server.app)


def test_health(monkeypatch):
    c = make_client(monkeypatch)
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["claude_ok"] is True


def test_analyze_endpoint(monkeypatch):
    c = make_client(monkeypatch)
    r = c.post("/api/analyze", json={"cv": {"kind": "text", "value": "Python analyst"},
                                     "offer": {"kind": "text", "value": "Need Python and Power BI"}})
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] >= 0
    assert "power bi" in {k.lower() for k in body["missing_keywords"]}


def test_platforms_endpoint(monkeypatch):
    c = make_client(monkeypatch)
    r = c.get("/api/platforms?side=applier")
    ids = {p["id"] for p in r.json()}
    assert "arbeitnow" in ids


def test_analyze_bad_url_returns_clean_error(monkeypatch):
    """A source that fails to fetch/extract must degrade to a clean JSON error,
    never an unhandled 500 stack trace bubbling out of the ASGI app."""
    c = make_client(monkeypatch)

    def _boom(value, kind, fetcher=None):
        raise httpx.ConnectError("could not connect")

    monkeypatch.setattr(server, "extract_text", _boom)
    r = c.post("/api/analyze", json={"cv": {"kind": "url", "value": "http://nonexistent.invalid/cv"},
                                     "offer": {"kind": "text", "value": "Need Python"}})
    assert r.status_code >= 400
    assert "error" in r.json()
