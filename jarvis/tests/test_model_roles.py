"""Engine plan: exact commands -> no model; uncertain intent -> tiny fast model; normal planning -> 4B planner;
hard planning -> deep model only when installed; every role lists models best-first."""
from __future__ import annotations

import asyncio

from jarvis.core.agent.loop import AgentRunner, is_hard_goal
from jarvis.core.llm.client import LLMError, LLMSettings, OllamaClient, model_candidates

SETTINGS = LLMSettings(fast_model="qwen3.5:2b, qwen3.5:0.8b, qwen3:1.7b", planner_model="qwen3.5:4b, llama3.2:latest",
                       chat_model="qwen3.5:4b, llama3.2:latest", vision_model="qwen3.5:4b, qwen2.5vl:3b",
                       deep_model="qwen3.6:35b-a3b")


def test_role_candidates_best_first_with_installed_fallback():
    assert model_candidates("qwen3.5:4b, llama3.2") == ["qwen3.5:4b", "llama3.2"]
    full = ["qwen3.5:2b", "qwen3.5:4b", "qwen3.6:35b-a3b", "qwen2.5vl:3b"]
    c = OllamaClient(SETTINGS)
    assert [c._resolve_from(r, full) for r in ("fast", "planner", "chat", "vision", "deep")] == \
        ["qwen3.5:2b", "qwen3.5:4b", "qwen3.5:4b", "qwen3.5:4b", "qwen3.6:35b-a3b"]
    old = ["qwen3:1.7b", "llama3.2:latest", "qwen2.5vl:3b"]
    c = OllamaClient(SETTINGS)
    assert [c._resolve_from(r, old) for r in ("fast", "planner", "vision", "deep")] == \
        ["qwen3:1.7b", "llama3.2:latest", "qwen2.5vl:3b", "llama3.2:latest"]  # deep falls back to the planner


def test_hard_goal_detection():
    assert not is_hard_goal("open chrome")
    assert not is_hard_goal("find the latest invoice and send it to my phone")
    assert is_hard_goal("compare the prices of pixel 9 on amazon and flipkart")
    assert is_hard_goal("find my resume, then attach it to an email, then send it to hr, and after that remind me tomorrow")


class _Client:
    """Planner fails twice with invalid JSON; the deep model answers."""

    def __init__(self, deep_installed: bool):
        self.deep_installed = deep_installed
        self.roles: list[str] = []

    async def resolve(self, role):
        return "qwen3.6:35b-a3b" if role == "deep" and self.deep_installed else "qwen3.5:4b"

    async def chat_json(self, messages, schema, role="chat", **kw):
        self.roles.append(role)
        if role != "deep":
            raise LLMError("Model did not return valid JSON")
        return {"thought": "", "action": "final_answer", "message": "Done with the big model."}


class _Registry:
    def list(self):
        return []

    def contains(self, name):
        return False


def _agent(client):
    agent = AgentRunner.__new__(AgentRunner)
    agent._client, agent.registry, agent.max_steps = client, _Registry(), 4
    return agent


def test_agent_escalates_to_deep_only_when_installed():
    state = {"goal": "g", "tools": ["x"], "messages": [{"role": "user", "content": "g"}], "steps": [], "calls": []}
    client = _Client(deep_installed=True)
    out = asyncio.run(_agent(client).run("open chrome", state=dict(state)))
    assert out.status == "done" and client.roles == ["planner", "deep"]
    client = _Client(deep_installed=False)
    out = asyncio.run(_agent(client).run("open chrome", state=dict(state)))
    assert out.status == "failed" and client.roles == ["planner"]
