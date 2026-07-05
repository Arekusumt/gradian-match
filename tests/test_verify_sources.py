from gradianmatch.verify_sources import extract_urls, classify_url, verify_sources

class FakeResp:
    def __init__(self, status, payload=None, url=""):
        self.status_code = status; self._p = payload or {}; self.url = url
    def json(self): return self._p

class FakeHttp:
    def __init__(self, routes): self.routes = routes
    def get(self, url, **kw): return self.routes[url]

def test_extract_and_classify():
    text = "See github.com/Arekusumt/gradian-sistema and https://linkedin.com/in/alex"
    urls = extract_urls(text)
    assert any("github.com" in u for u in urls)
    assert classify_url("https://github.com/a/b") == "github"
    assert classify_url("https://linkedin.com/in/x") == "linkedin"

def test_github_repo_verified():
    api = "https://api.github.com/repos/Arekusumt/gradian-sistema"
    http = FakeHttp({
        "https://github.com/Arekusumt/gradian-sistema": FakeResp(200, url=api),
        api: FakeResp(200, {"stargazers_count": 3, "owner": {"login": "Arekusumt"},
                            "pushed_at": "2026-07-01T00:00:00Z", "language": "Python"}),
    })
    results = verify_sources("github.com/Arekusumt/gradian-sistema", http)
    gh = [r for r in results if r.kind == "github"][0]
    assert gh.ok and gh.details["owner"] == "Arekusumt" and gh.details["stars"] == 3

def test_dead_link_flagged():
    http = FakeHttp({"https://example.com/x": FakeResp(404, url="https://example.com/x")})
    results = verify_sources("https://example.com/x", http)
    assert results[0].ok is False
