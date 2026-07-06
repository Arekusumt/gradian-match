from gradianmatch.verify_sources import extract_urls, classify_url, verify_sources

class FakeResp:
    def __init__(self, status, payload=None, url=""):
        self.status_code = status; self._p = payload or {}; self.url = url
    def json(self): return self._p

class FakeHttp:
    def __init__(self, routes): self.routes = routes
    def get(self, url, **kw): return self.routes[url]

def test_extract_and_classify():
    text = "See github.com/sam-rivera-dev/open-portfolio and https://linkedin.com/in/sam-rivera"
    urls = extract_urls(text)
    assert any("github.com" in u for u in urls)
    assert classify_url("https://github.com/a/b") == "github"
    assert classify_url("https://linkedin.com/in/x") == "linkedin"

def test_github_repo_verified():
    api = "https://api.github.com/repos/sam-rivera-dev/open-portfolio"
    http = FakeHttp({
        "https://github.com/sam-rivera-dev/open-portfolio": FakeResp(200, url=api),
        api: FakeResp(200, {"stargazers_count": 3, "owner": {"login": "sam-rivera-dev"},
                            "pushed_at": "2026-07-01T00:00:00Z", "language": "Python"}),
    })
    results = verify_sources("github.com/sam-rivera-dev/open-portfolio", http)
    gh = [r for r in results if r.kind == "github"][0]
    assert gh.ok and gh.details["owner"] == "sam-rivera-dev" and gh.details["stars"] == 3

def test_dead_link_flagged():
    http = FakeHttp({"https://example.com/x": FakeResp(404, url="https://example.com/x")})
    results = verify_sources("https://example.com/x", http)
    assert results[0].ok is False

def test_verify_isolates_per_url_failure():
    class R:
        def __init__(self, status): self.status_code = status
        def json(self): return {}
    class Boom:
        def get(self, url, **kw):
            if "api.github.com" in url:
                raise ConnectionError("down")
            return R(200)
    results = verify_sources("github.com/a/b and https://example.com/ok", Boom())
    assert len(results) == 2
    assert any(r.kind == "github" and r.ok is False for r in results)
    assert any(r.kind == "web" and r.ok is True for r in results)
