import pytest
from gradianmatch import config
from gradianmatch.ai_client import (
    ApiClient, build_ai_client, active_backend, describe_backend)
from gradianmatch.claude_client import ClaudeClient, ClaudeError


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Msg:
    def __init__(self, text):
        self.content = [_Block(text)]


class _Messages:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0

    def create(self, **kw):
        out = self._outputs[min(self.calls, len(self._outputs) - 1)]
        self.calls += 1
        return _Msg(out)


class FakeAnthropic:
    def __init__(self, outputs):
        self.messages = _Messages(outputs)

    def with_options(self, **kw):
        return self


def test_api_run_json_parses_text_block():
    c = ApiClient(client=FakeAnthropic(['{"score": 91}']), model="m")
    assert c.run_json("hi") == {"score": 91}


def test_api_run_json_parses_fenced_json():
    c = ApiClient(client=FakeAnthropic(["```json\n{\"ok\": true}\n```"]), model="m")
    assert c.run_json("hi") == {"ok": True}


def test_api_run_json_repairs_once_then_raises():
    fake = FakeAnthropic(["not json", "still not json"])
    c = ApiClient(client=fake, model="m")
    with pytest.raises(ClaudeError):
        c.run_json("hi")
    assert fake.messages.calls == 2  # original + one repair attempt


def test_api_wraps_transport_errors():
    class Boom:
        def with_options(self, **kw):
            return self

        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                raise RuntimeError("network down")
    c = ApiClient(client=Boom(), model="m")
    with pytest.raises(ClaudeError):
        c.run_json("hi")


def test_active_backend_auto_prefers_api_when_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert active_backend(config.Config(backend="auto", anthropic_api_key="sk-x")) == "api"
    assert active_backend(config.Config(backend="auto", anthropic_api_key=None)) == "cli"


def test_active_backend_respects_explicit_choice(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert active_backend(config.Config(backend="cli", anthropic_api_key="sk-x")) == "cli"
    assert active_backend(config.Config(backend="api", anthropic_api_key=None)) == "api"


def test_build_ai_client_picks_backend(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert isinstance(build_ai_client(config.Config(anthropic_api_key="sk-x")), ApiClient)
    assert isinstance(build_ai_client(config.Config(anthropic_api_key=None)), ClaudeClient)


def test_describe_backend_shape():
    d = describe_backend(config.Config(anthropic_api_key="sk-x", model="claude-sonnet-5"))
    assert d["backend"] == "api" and d["model"] == "claude-sonnet-5"
    d2 = describe_backend(config.Config(backend="cli"))
    assert d2["backend"] == "cli"


def test_api_check_available_false_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    ok, msg = ApiClient(api_key=None, client=FakeAnthropic([""])).check_available()
    assert ok is False and "ANTHROPIC_API_KEY" in msg
