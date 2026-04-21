"""Crew/agent framework primitives for local Ollama-backed execution."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import logging
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class AgentSettings:
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "ollama/llama3"
    crew_llm_provider: str = "ollama"
    temperature: float = 0.2
    request_timeout_s: float = 5.0
    log_level: str = "INFO"


def get_agent_settings() -> AgentSettings:
    """Resolve agent settings from environment variables."""
    return AgentSettings(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "ollama/llama3"),
        crew_llm_provider=os.getenv("CREW_LLM_PROVIDER", "ollama"),
        temperature=float(os.getenv("CREW_TEMPERATURE", "0.2")),
        request_timeout_s=float(os.getenv("CREW_REQUEST_TIMEOUT", "5.0")),
        log_level=os.getenv("CREW_LOG_LEVEL", "INFO"),
    )


def setup_agent_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("ahimp.agents")
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def _fetch_ollama_tags(base_url: str, timeout_s: float) -> tuple[int, dict]:
    endpoint = f"{base_url.rstrip('/')}/api/tags"
    request = Request(endpoint, method="GET")
    with urlopen(request, timeout=timeout_s) as response:
        status = int(getattr(response, "status", 200))
        payload = json.loads(response.read().decode("utf-8"))
        return status, payload


def check_ollama_connectivity(
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> dict:
    """Check whether local Ollama is reachable and returns model metadata."""
    settings = get_agent_settings()
    resolved_url = base_url or settings.ollama_base_url
    resolved_timeout = timeout_s or settings.request_timeout_s

    try:
        status_code, payload = _fetch_ollama_tags(resolved_url, resolved_timeout)
        model_names = [m.get("name", "") for m in payload.get("models", [])]
        return {
            "reachable": True,
            "status_code": status_code,
            "models": model_names,
            "error": None,
        }
    except HTTPError as exc:
        return {
            "reachable": False,
            "status_code": int(exc.code),
            "models": [],
            "error": str(exc),
        }
    except URLError as exc:
        return {
            "reachable": False,
            "status_code": None,
            "models": [],
            "error": str(exc.reason),
        }
    except Exception as exc:
        return {
            "reachable": False,
            "status_code": None,
            "models": [],
            "error": str(exc),
        }


class ToolRegistry:
    """Simple registry for named callable tools used by agents."""

    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, func: Callable[..., Any]) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = func

    def get(self, name: str) -> Callable[..., Any]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def execute(self, name: str, *args, **kwargs) -> Any:
        return self.get(name)(*args, **kwargs)

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())


@dataclass
class AgentTask:
    name: str
    description: str
    payload: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for AHIMP task-specific agents."""

    def __init__(
        self,
        name: str,
        settings: AgentSettings | None = None,
        registry: ToolRegistry | None = None,
        logger: logging.Logger | None = None,
    ):
        self.name = name
        self.settings = settings or get_agent_settings()
        self.registry = registry or ToolRegistry()
        self.logger = logger or setup_agent_logging(self.settings.log_level)

    @abstractmethod
    def execute(self, task: AgentTask, context: dict[str, Any] | None = None) -> dict:
        """Execute the task-specific logic and return a structured result."""

    def run(self, task: AgentTask, context: dict[str, Any] | None = None) -> dict:
        self.logger.info("Agent '%s' executing task '%s'", self.name, task.name)
        try:
            result = self.execute(task, context or {})
            return {
                "agent": self.name,
                "task": task.name,
                "ok": True,
                "result": result,
            }
        except Exception as exc:
            self.logger.exception("Agent '%s' failed", self.name)
            return {
                "agent": self.name,
                "task": task.name,
                "ok": False,
                "error": str(exc),
            }


class TaskRunner:
    """Run one task through one agent with common context."""

    def run(
        self,
        agent: BaseAgent,
        task: AgentTask,
        context: dict[str, Any] | None = None,
    ) -> dict:
        return agent.run(task, context=context)


class CrewOrchestrator:
    """Coordinate multiple agents across a sequence of tasks."""

    def __init__(self, agents: list[BaseAgent]):
        self._agents = {agent.name: agent for agent in agents}
        self._runner = TaskRunner()

    def run_pipeline(
        self,
        pipeline: list[tuple[str, AgentTask]],
        context: dict[str, Any] | None = None,
    ) -> list[dict]:
        shared = context.copy() if context else {}
        results: list[dict] = []

        for agent_name, task in pipeline:
            if agent_name not in self._agents:
                results.append(
                    {
                        "agent": agent_name,
                        "task": task.name,
                        "ok": False,
                        "error": f"Agent not registered: {agent_name}",
                    }
                )
                continue
            out = self._runner.run(self._agents[agent_name], task, context=shared)
            results.append(out)
            if out.get("ok"):
                shared[task.name] = out.get("result")
        return results


def build_crewai_llm(settings: AgentSettings | None = None):
    """Build a CrewAI-compatible local Ollama LLM when crewai is available."""
    cfg = settings or get_agent_settings()
    try:
        from crewai import LLM  # type: ignore

        return LLM(
            model=cfg.ollama_model,
            base_url=cfg.ollama_base_url,
            temperature=cfg.temperature,
        )
    except Exception:
        return None
