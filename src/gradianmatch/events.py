# src/gradianmatch/events.py
"""Progress events for the 'agentic OS' live view.

The orchestrators (analyze / regenerate / recruiter) optionally take an ``emit``
callback and call it as each agent starts and finishes work. The FastAPI layer runs
the blocking orchestration in a worker thread and streams those events to the browser
as Server-Sent-Events, so the user sees which agent is running, what it's doing, and a
progress bar — for the first run AND for every regeneration.

Event shapes (all JSON objects with a ``type``):
  {"type":"start","run":"analyze","agents":[{"id","name","desc"}...]}
  {"type":"agent","agent":"analyst","status":"running"|"done"|"error","label":str,"pct":int}
  {"type":"result","data":{...}}      # the same payload the non-stream endpoint returns
  {"type":"error","message":str}
  {"type":"done"}
"""
from __future__ import annotations

import json
import queue
import threading
from typing import Callable, Iterator

Emit = Callable[[dict], None]


def noop(_event: dict) -> None:
    """Default emit: orchestrators run identically when nobody is listening."""


def agent_event(agent: str, status: str, label: str = "", pct: int | None = None) -> dict:
    ev = {"type": "agent", "agent": agent, "status": status}
    if label:
        ev["label"] = label
    if pct is not None:
        ev["pct"] = int(max(0, min(100, pct)))
    return ev


class EventStream:
    """Bridges a blocking worker (run in a thread) to a Server-Sent-Events generator."""

    _SENTINEL = object()

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()

    def emit(self, event: dict) -> None:
        self._q.put(event)

    def _close(self) -> None:
        self._q.put(self._SENTINEL)

    def run_in_thread(self, worker: Callable[[Emit], None]) -> None:
        """Start ``worker(emit)`` on a daemon thread; always terminate the stream."""
        def target() -> None:
            try:
                worker(self.emit)
            except Exception as e:  # noqa: BLE001 — surface as a clean error event
                self.emit({"type": "error", "message": str(e) or type(e).__name__})
            finally:
                self.emit({"type": "done"})
                self._close()

        threading.Thread(target=target, daemon=True).start()

    def sse(self, keepalive: float = 15.0) -> Iterator[str]:
        """Yield SSE frames until the worker finishes.

        Keepalive comment lines keep the connection warm during long model calls
        (a single Opus response can take a while) without confusing the client parser.
        """
        while True:
            try:
                item = self._q.get(timeout=keepalive)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if item is self._SENTINEL:
                return
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
