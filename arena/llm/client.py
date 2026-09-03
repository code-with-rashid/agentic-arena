"""A tiny OpenAI-compatible chat client built on the standard library.

Used directly by the `vanilla` baseline adapter and available to any other adapter
that wants a dependency-free path. It also accumulates token usage so the harness
can report real numbers even when a framework hides them.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatResponse:
    content: str
    tool_calls: list[dict[str, Any]]  # [{"id","name","arguments"(str)}]
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    raw: dict[str, Any]


@dataclass
class ChatClient:
    base_url: str
    api_key: str
    model: str
    timeout_s: float = 60.0
    # Default sampling temperature for every call this client makes. The harness
    # passes `ArenaConfig.temperature` here so the baseline is pinned the same way
    # the framework adapters are; a per-call argument still overrides it.
    temperature: float = 0.0
    prompt_tokens: int = field(default=0, init=False)
    completion_tokens: int = field(default=0, init=False)
    calls: int = field(default=0, init=False)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        temperature: float | None = None,
    ) -> ChatResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc

        self.calls += 1
        usage = payload.get("usage") or {}
        pt = int(usage.get("prompt_tokens", 0))
        ct = int(usage.get("completion_tokens", 0))
        self.prompt_tokens += pt
        self.completion_tokens += ct

        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls: list[dict[str, Any]] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            tool_calls.append(
                {
                    "id": tc.get("id", f"call_{len(tool_calls)}"),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}"),
                }
            )
        return ChatResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            prompt_tokens=pt,
            completion_tokens=ct,
            raw=payload,
        )
