import json
import pytest
from gradianmatch.claude_client import ClaudeClient, ClaudeError

def make_cli_json(payload_text: str) -> str:
    # Mimics `claude -p --output-format json`: a JSON envelope with a "result" string.
    return json.dumps({"type": "result", "result": payload_text})

def test_run_json_parses_plain_json_result():
    runner = lambda argv, timeout: make_cli_json('{"score": 87}')
    c = ClaudeClient(runner=runner)
    assert c.run_json("hi") == {"score": 87}

def test_run_json_parses_fenced_json_result():
    fenced = "```json\n{\"ok\": true}\n```"
    runner = lambda argv, timeout: make_cli_json(fenced)
    c = ClaudeClient(runner=runner)
    assert c.run_json("hi") == {"ok": True}

def test_run_json_repairs_once_then_raises():
    calls = {"n": 0}
    def runner(argv, timeout):
        calls["n"] += 1
        return make_cli_json("not json at all")
    c = ClaudeClient(runner=runner)
    with pytest.raises(ClaudeError):
        c.run_json("hi")
    assert calls["n"] == 2  # original + one repair attempt

def test_check_available_false_when_binary_missing():
    def runner(argv, timeout):
        raise FileNotFoundError("claude")
    ok, msg = ClaudeClient(runner=runner).check_available()
    assert ok is False and "Claude Code" in msg
