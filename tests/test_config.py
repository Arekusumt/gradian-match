from gradianmatch import config

def test_paths_point_into_project():
    assert config.DATA_DIR.name == "data"
    assert config.RUBRICS_DIR.name == "rubrics"

def test_env_reads_optional_keys(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    monkeypatch.delenv("JOOBLE_KEY", raising=False)
    monkeypatch.setenv("ADZUNA_APP_ID", "abc")
    cfg = config.load_config()
    assert cfg.adzuna_app_id == "abc"
    assert cfg.github_token is None
