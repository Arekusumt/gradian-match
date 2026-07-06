# src/gradianmatch/claude_client.py
from __future__ import annotations
import json, re, shutil, subprocess
from typing import Callable

class ClaudeError(RuntimeError):
    pass

Runner = Callable[[list[str], int], str]

def _default_runner(argv: list[str], timeout: int) -> str:
    exe = shutil.which(argv[0]) or argv[0]
    proc = subprocess.run([exe, *argv[1:]], capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8")
    if proc.returncode != 0:
        raise ClaudeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:400]}")
    return proc.stdout

_FENCE = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.DOTALL)

def _extract_json(text: str) -> dict | list:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _FENCE.search(text)
    if m:
        return json.loads(m.group(1))
    # last resort: first {...} or [...] span
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = text.find(open_c), text.rfind(close_c)
        if i != -1 and j > i:
            return json.loads(text[i:j + 1])
    raise json.JSONDecodeError("no json found", text, 0)

class ClaudeClient:
    def __init__(self, runner: Runner | None = None, model: str | None = None):
        self._runner = runner or _default_runner
        self._model = model

    def _invoke(self, prompt: str, timeout: int) -> str:
        argv = ["claude", "-p", prompt, "--output-format", "json"]
        if self._model:
            argv += ["--model", self._model]
        raw = self._runner(argv, timeout)
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            return raw  # some versions print the text directly
        if isinstance(envelope, dict):
            if envelope.get("is_error"):
                raise ClaudeError(
                    "Claude returned an error: "
                    f"{envelope.get('result') or envelope.get('subtype') or raw[:300]}")
            return envelope.get("result", raw)
        return raw

    def _call(self, prompt: str, timeout: int) -> str:
        """Invoke the CLI, normalizing any transport failure into ClaudeError."""
        try:
            return self._invoke(prompt, timeout)
        except ClaudeError:
            raise
        except Exception as e:  # subprocess.TimeoutExpired, FileNotFoundError, etc.
            raise ClaudeError(f"Claude Code call failed: {type(e).__name__}: {e}") from e

    def run_json(self, prompt: str, timeout: int = 300) -> dict | list:
        text = self._call(prompt, timeout)
        try:
            return _extract_json(text)
        except json.JSONDecodeError:
            repair = (prompt + "\n\nYour previous answer was not valid JSON. "
                      "Reply with ONLY the JSON, no prose, no code fences.")
            text2 = self._call(repair, timeout)
            try:
                return _extract_json(text2)
            except json.JSONDecodeError as e:
                raise ClaudeError(f"Claude did not return valid JSON: {text2[:300]}") from e

    def check_available(self) -> tuple[bool, str]:
        if shutil.which("claude") is None and self._runner is _default_runner:
            return False, ("Claude Code CLI not found. Install it and sign in "
                           "(https://claude.com/claude-code), then reopen Gradian Match.")
        try:
            self._runner(["claude", "--version"], 20)
            return True, "ok"
        except FileNotFoundError:
            return False, "Claude Code CLI not found on PATH. Install and sign in first."
        except Exception as e:  # noqa: BLE001
            return False, f"Claude Code check failed: {e}"
