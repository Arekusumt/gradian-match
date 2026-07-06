from urllib.parse import unquote_plus
from gradianmatch.recruiter.talent_search import github_search, xray_query, Candidate


class FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._p = payload or {}

    def json(self):
        return self._p


class FakeHttp:
    def __init__(self, resp):
        self.resp = resp
        self.last_url = None

    def get(self, url, **kw):
        self.last_url = url
        return self.resp


class BoomHttp:
    def get(self, url, **kw):
        raise ConnectionError("down")


def test_github_search_maps_items_to_candidates():
    http = FakeHttp(FakeResp(200, {"items": [
        {"login": "alice", "name": "Alice", "html_url": "https://github.com/alice"}]}))
    out = github_search({"language": "Python", "location": "Barcelona",
                         "keywords": ["data analyst"]}, http)
    assert out == [Candidate(login="alice", name="Alice",
                             url="https://github.com/alice", source="github")]
    # query carries the right operators (url-encoded)
    q = unquote_plus(http.last_url)
    assert 'language:Python' in q
    assert 'location:Barcelona' in q
    assert 'type:user' in q
    assert '"data analyst"' in q


def test_github_search_name_falls_back_to_login():
    http = FakeHttp(FakeResp(200, {"items": [
        {"login": "bob", "html_url": "https://github.com/bob"}]}))
    out = github_search({"language": "Go"}, http)
    assert out[0].name == "bob"


def test_github_search_accepts_string_keywords():
    http = FakeHttp(FakeResp(200, {"items": []}))
    github_search({"keywords": "sql developer"}, http)
    assert '"sql developer"' in unquote_plus(http.last_url)


def test_github_search_empty_or_error_returns_list():
    assert github_search({}, FakeHttp(FakeResp(200, {"items": []}))) == []
    assert github_search({}, FakeHttp(FakeResp(403, {}))) == []
    assert github_search({}, BoomHttp()) == []


def test_xray_linkedin_with_location():
    s = xray_query("data analyst", "Barcelona")
    assert 'site:linkedin.com/in' in s
    assert '("data analyst")' in s
    assert '"Barcelona"' in s


def test_xray_linkedin_without_location_omits_clause():
    s = xray_query("data analyst")
    assert 'site:linkedin.com/in' in s
    assert '("data analyst")' in s
    assert '""' not in s  # no empty location clause


def test_xray_github_site_operator():
    s = xray_query("backend engineer", "Reus", site="github")
    assert 'site:github.com' in s
    assert '"backend engineer"' in s
    assert '"Reus"' in s
