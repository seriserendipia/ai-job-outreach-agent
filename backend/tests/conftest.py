"""Shared fixtures: a fake-LLM scenario harness that lets us drive every node
without real API keys, and a FastAPI TestClient.

Design:
- A `Scenario` holds queues of canned responses, keyed by Pydantic model class
  for `.with_structured_output(Model)` calls and a single queue of AIMessage
  for `.bind_tools(...)` calls (used inside the recruiter_finder ReAct loop).
- `FakeLLM` mimics the slice of ChatOpenAI's surface that our nodes actually use.
- The `mock_llm` fixture patches `make_llm` in every node module so the nodes
  see a FakeLLM instead of a real ChatOpenAI, and patches `web_search` in the
  recruiter_finder module with a `FakeTool` that returns canned strings.
"""
import importlib
from collections import deque
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

# Node modules that import `make_llm` into their namespace. We have to patch
# each module's local binding (not just `app.llm.make_llm`) because the nodes
# do `from app.llm import make_llm`.
_NODE_MODULES = [
    "app.graph.nodes.jd_analyzer",
    "app.graph.nodes.recruiter_finder",
    "app.graph.nodes.writer",
    "app.graph.nodes.critic",
]


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class Scenario:
    """Canned responses for one test run."""

    def __init__(self) -> None:
        # Pydantic model class -> deque of response instances (or callables).
        self._structured: dict[type, deque] = {}
        # AIMessage queue for the bind_tools(...).invoke() path.
        self._tool_replies: deque = deque()

    def add_structured(self, model_cls: type, *responses: Any) -> "Scenario":
        self._structured.setdefault(model_cls, deque()).extend(responses)
        return self

    def add_tool_reply(self, *ai_messages: Any) -> "Scenario":
        self._tool_replies.extend(ai_messages)
        return self

    # Internal —
    def pop_structured(self, model_cls: type) -> Any:
        q = self._structured.get(model_cls)
        if not q:
            raise AssertionError(
                f"No structured response queued for {model_cls.__name__} "
                f"(node tried to call an LLM the test didn't prepare for)"
            )
        item = q.popleft()
        return item(model_cls) if callable(item) else item

    def pop_tool_reply(self) -> Any:
        if not self._tool_replies:
            raise AssertionError(
                "No tool-loop response queued (recruiter_finder iterated more "
                "times than the test prepared for)"
            )
        return self._tool_replies.popleft()


class _StructuredRunner:
    def __init__(self, scenario: Scenario, model_cls: type) -> None:
        self._scenario, self._model = scenario, model_cls

    def invoke(self, _messages):  # noqa: D401
        return self._scenario.pop_structured(self._model)


class _ToolRunner:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario

    def invoke(self, _messages):
        return self._scenario.pop_tool_reply()


class FakeLLM:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario

    def with_structured_output(self, model_cls: type):
        return _StructuredRunner(self._scenario, model_cls)

    def bind_tools(self, _tools):
        return _ToolRunner(self._scenario)


class FakeTool:
    """Drop-in for langchain `@tool`-decorated web_search."""

    def __init__(self, response: str | Callable[[dict], str]) -> None:
        self._response = response

    def invoke(self, args: dict) -> str:
        return self._response(args) if callable(self._response) else self._response


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture
def mock_llm(monkeypatch):
    """Patch make_llm in each node module. Returns the Scenario.

    We grab the module objects via importlib because `nodes/__init__.py`
    re-exports the node functions under the same names as their submodules,
    which shadows the module attribute on the package and breaks dotted-path
    monkeypatching.
    """
    scenario = Scenario()
    factory = lambda *a, **kw: FakeLLM(scenario)  # noqa: E731
    for name in _NODE_MODULES:
        monkeypatch.setattr(importlib.import_module(name), "make_llm", factory)
    return scenario


@pytest.fixture
def fake_web_search(monkeypatch):
    """Returns a setter; callers pass a string (or a callable) for the search result."""
    finder_mod = importlib.import_module("app.graph.nodes.recruiter_finder")

    def install(response):
        monkeypatch.setattr(finder_mod, "web_search", FakeTool(response))

    return install


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)
