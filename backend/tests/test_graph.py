"""End-to-end graph runs with canned LLM responses.

These tests verify the three patterns are wired correctly:
  - hierarchical delegation (supervisor routes around already-done steps)
  - ReAct (recruiter_finder is reached and finishes)
  - self-reflection (writer<->critic loop iterates and terminates)

Trick: each test queues only the LLM responses it expects to need. If the graph
mistakenly visits another node, the fake's queue is empty and the test fails
loudly — which gives us strong negative assertions without extra plumbing.
"""
import uuid

from langchain_core.messages import AIMessage

from app.graph.graph import graph
from app.graph.state import Critique, EmailDraft, JobInfo, RecruiterResult


def _job() -> JobInfo:
    return JobInfo(company="Acme", title="AI Engineer", key_requirements=["LangGraph"])


def _passing() -> Critique:
    return Critique(
        specificity=5, tone=5, no_placeholders=True, length_ok=True,
        no_hallucination=True, passed=True, feedback="",
    )


def _failing() -> Critique:
    return Critique(
        specificity=2, tone=3, no_placeholders=True, length_ok=True,
        no_hallucination=True, passed=False, feedback="add specifics",
    )


def _new_thread() -> dict:
    return {"configurable": {"thread_id": uuid.uuid4().hex}}


def test_first_generate_critic_passes_immediately(mock_llm, fake_web_search):
    """analyze -> find -> write -> critic(pass) -> end."""
    fake_web_search("search result")
    mock_llm.add_structured(JobInfo, _job())
    mock_llm.add_tool_reply(AIMessage(content="nothing"))  # finder breaks immediately
    mock_llm.add_structured(
        RecruiterResult,
        RecruiterResult(email="r@acme.com", candidate_urls=[], source="search"),
    )
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="s", body="b"))
    mock_llm.add_structured(Critique, _passing())

    out = graph.invoke(
        {"resume_text": "R", "page_text": "Acme posting", "user_message": ""},
        config=_new_thread(),
    )
    assert out["draft"].subject == "s"
    assert out["recruiter"].email == "r@acme.com"
    assert out["critique"].passed is True
    assert out.get("revision_count", 0) == 0


def test_reflection_loop_iterates_then_passes(mock_llm, fake_web_search):
    """Critic fails the first draft, writer revises, critic passes the second."""
    fake_web_search("result")
    mock_llm.add_structured(JobInfo, _job())
    mock_llm.add_tool_reply(AIMessage(content="nothing"))
    mock_llm.add_structured(
        RecruiterResult,
        RecruiterResult(email=None, candidate_urls=[], source="none"),
    )
    mock_llm.add_structured(
        EmailDraft,
        EmailDraft(subject="first", body="generic"),
        EmailDraft(subject="second", body="specific"),
    )
    mock_llm.add_structured(Critique, _failing(), _passing())

    out = graph.invoke(
        {"resume_text": "R", "page_text": "Acme posting", "user_message": ""},
        config=_new_thread(),
    )
    assert out["draft"].subject == "second"
    assert out["critique"].passed is True
    assert out["revision_count"] == 1


def test_jd_email_shortcut_skips_recruiter_finder(mock_llm):
    """When the posting contains an email, jd_analyzer fills the recruiter
    directly. No tool_reply / RecruiterResult is queued — if the supervisor
    mistakenly ran recruiter_finder, the test would assertion-error inside the
    fake's empty queue."""
    mock_llm.add_structured(JobInfo, _job())
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="s", body="b"))
    mock_llm.add_structured(Critique, _passing())

    out = graph.invoke(
        {"resume_text": "R", "page_text": "Acme is hiring. Apply at jane@acme.com",
         "user_message": ""},
        config=_new_thread(),
    )
    assert out["recruiter"].source == "jd"
    assert out["recruiter"].email == "jane@acme.com"


def test_follow_up_turn_resumes_state_and_skips_steps(mock_llm, fake_web_search):
    """A follow-up call on the same thread_id with user_message should only run
    writer + critic. If supervisor mistakenly re-ran jd_analyzer or
    recruiter_finder, their unqueued LLM calls would fail the test."""
    fake_web_search("result")
    thread = _new_thread()

    # --- turn 1: full cold-start flow ---
    mock_llm.add_structured(JobInfo, _job())
    mock_llm.add_tool_reply(AIMessage(content="nothing"))
    mock_llm.add_structured(
        RecruiterResult,
        RecruiterResult(email="r@acme.com", candidate_urls=[], source="search"),
    )
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="v1", body="b"))
    mock_llm.add_structured(Critique, _passing())
    out1 = graph.invoke(
        {"resume_text": "R", "page_text": "Acme", "user_message": ""}, config=thread
    )
    assert out1["draft"].subject == "v1"

    # --- turn 2: only writer + critic should run ---
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="v2-shorter", body="b2"))
    mock_llm.add_structured(Critique, _passing())
    out2 = graph.invoke({"user_message": "make it shorter"}, config=thread)
    assert out2["draft"].subject == "v2-shorter"
    assert out2.get("user_message", "") == ""  # consumed by writer
    # Job + recruiter survive from turn 1.
    assert out2["job"].company == "Acme"
    assert out2["recruiter"].email == "r@acme.com"
