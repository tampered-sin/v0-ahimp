from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.config import (
    AgentTask,
    BaseAgent,
    CrewOrchestrator,
    ToolRegistry,
    check_ollama_connectivity,
    get_agent_settings,
)


def test_get_agent_settings_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "ollama/llama3")
    monkeypatch.setenv("CREW_LOG_LEVEL", "DEBUG")

    cfg = get_agent_settings()

    assert cfg.ollama_base_url == "http://localhost:11434"
    assert cfg.ollama_model == "ollama/llama3"
    assert cfg.log_level == "DEBUG"


def test_check_ollama_connectivity_success(monkeypatch):
    monkeypatch.setattr(
        "agents.config._fetch_ollama_tags",
        lambda base_url, timeout_s: (200, {"models": [{"name": "llama3"}]}),
    )

    result = check_ollama_connectivity()

    assert result["reachable"] is True
    assert result["status_code"] == 200
    assert result["models"] == ["llama3"]


def test_check_ollama_connectivity_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("connection failed")

    monkeypatch.setattr("agents.config._fetch_ollama_tags", _raise)

    result = check_ollama_connectivity()

    assert result["reachable"] is False
    assert "connection failed" in result["error"]


def test_tool_registry_register_execute():
    registry = ToolRegistry()
    registry.register("add", lambda a, b: a + b)

    assert registry.list_tools() == ["add"]
    assert registry.execute("add", 2, 3) == 5

    with pytest.raises(ValueError):
        registry.register("add", lambda a, b: a - b)


class _EchoAgent(BaseAgent):
    def execute(self, task: AgentTask, context=None):
        context = context or {}
        return {
            "description": task.description,
            "payload": task.payload,
            "context_keys": sorted(context.keys()),
        }


def test_crew_orchestrator_runs_pipeline():
    agent = _EchoAgent(name="ingestion-agent")
    orchestrator = CrewOrchestrator([agent])

    pipeline = [
        (
            "ingestion-agent",
            AgentTask(name="validate_input", description="validate", payload={"records": 3}),
        )
    ]

    result = orchestrator.run_pipeline(pipeline, context={"trace_id": "abc"})

    assert len(result) == 1
    assert result[0]["ok"] is True
    assert result[0]["result"]["payload"]["records"] == 3
