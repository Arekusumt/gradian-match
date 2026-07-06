# src/gradianmatch/ai_client.py
"""The single door to the AI, over two interchangeable local backends.

Both backends expose the same tiny surface used across the app —
``run_json(prompt, timeout) -> dict|list`` and ``check_available() -> (bool, str)`` —
so every agent (Analyst / Tailor / Critic / Examiner / Sourcer / …) is backend-agnostic.

- **CLI backend** (`ClaudeClient`, in :mod:`gradianmatch.claude_client`): shells out to the
  installer's own ``claude`` Code CLI. Zero API keys, uses their subscription. Heavier per
  call (loads the Claude Code harness) but needs nothing bought.
- **API backend** (`ApiClient`, here): the official ``anthropic`` SDK with the user's own
  ``ANTHROPIC_API_KEY``. Far lighter/faster per call (no harness) — the recommended path for
  the multi-call regenerate loop.

Selection is driven by :func:`build_ai_client` from the :class:`~gradianmatch.config.Config`.
Everything stays **local**; nothing is stored or sent anywhere but the user's own AI account.
"""
from __future__ import annotations

from gradianmatch import config
from gradianmatch.claude_client import ClaudeClient, ClaudeError, _extract_json

# One generous default: the regenerate loop chains several calls; a single slow model
# response must not read as a crash. CLI calls (Claude Code harness) are the slow case.
DEFAULT_TIMEOUT = 300


class ApiClient:
    """Direct Anthropic API backend. Same interface as :class:`ClaudeClient`."""

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 client=None):
        self._model = model or config.DEFAULT_API_MODEL
        self._api_key = api_key
        self._client = client  # injectable for tests; built lazily otherwise

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:  # pragma: no cover - depends on install
                raise ClaudeError(
                    "The 'anthropic' package is not installed. Run "
                    "`pip install -r requirements.txt`, or switch to the Claude Code "
                    "backend (GM_BACKEND=cli).") from e
            # api_key=None lets the SDK resolve ambient credentials (env or `ant` profile).
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _complete(self, prompt: str, timeout: int) -> str:
        client = self._get_client()
        try:
            msg = client.with_options(timeout=timeout).messages.create(
                model=self._model,
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}],
            )
        except ClaudeError:
            raise
        except Exception as e:  # anthropic.APIError, timeouts, etc.
            raise ClaudeError(f"Anthropic API call failed: {type(e).__name__}: {e}") from e
        parts = [getattr(b, "text", "") for b in getattr(msg, "content", [])
                 if getattr(b, "type", None) == "text"]
        return "".join(parts)

    def run_json(self, prompt: str, timeout: int = DEFAULT_TIMEOUT):
        text = self._complete(prompt, timeout)
        try:
            return _extract_json(text)
        except Exception:
            repair = (prompt + "\n\nYour previous answer was not valid JSON. "
                      "Reply with ONLY the JSON, no prose, no code fences.")
            text2 = self._complete(repair, timeout)
            try:
                return _extract_json(text2)
            except Exception as e:
                raise ClaudeError(
                    f"The model did not return valid JSON: {text2[:300]}") from e

    def check_available(self) -> tuple[bool, str]:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, ("The 'anthropic' package is not installed. Run "
                           "`pip install -r requirements.txt`.")
        # Ambient credentials (an `ant auth login` profile) can authenticate even with no
        # explicit key, so a missing ANTHROPIC_API_KEY is only a soft warning.
        if not (self._api_key or _ambient_api_key()):
            return False, ("No ANTHROPIC_API_KEY found. Add it to .env, or use the "
                           "Claude Code backend (GM_BACKEND=cli).")
        return True, "ok"


def _ambient_api_key() -> str | None:
    import os
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")


def active_backend(cfg: config.Config) -> str:
    """Which backend :func:`build_ai_client` will pick: 'api' or 'cli'."""
    if cfg.backend == "api":
        return "api"
    if cfg.backend == "cli":
        return "cli"
    # auto: prefer the API backend when a key is configured; else Claude Code.
    return "api" if (cfg.anthropic_api_key or _ambient_api_key()) else "cli"


def build_ai_client(cfg: config.Config):
    """Construct the AI client for the configured backend.

    Returns an object with ``run_json`` and ``check_available`` — either an
    :class:`ApiClient` or a :class:`~gradianmatch.claude_client.ClaudeClient`.
    """
    if active_backend(cfg) == "api":
        return ApiClient(api_key=cfg.anthropic_api_key, model=cfg.model)
    # CLI: model=None means "use the user's own Claude Code default model".
    return ClaudeClient(model=cfg.model)


def describe_backend(cfg: config.Config) -> dict:
    """A small, UI-friendly description of the active backend + its model."""
    backend = active_backend(cfg)
    if backend == "api":
        return {"backend": "api", "label": "Anthropic API",
                "model": cfg.model or config.DEFAULT_API_MODEL}
    return {"backend": "cli", "label": "Claude Code",
            "model": cfg.model or "your Claude Code default"}
