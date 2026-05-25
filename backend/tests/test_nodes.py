"""Node-level tests driven by canned LLM responses (no real API calls)."""
from langchain_core.messages import AIMessage

from app.graph.nodes.critic import critic as critic_node
from app.graph.nodes.jd_analyzer import jd_analyzer
from app.graph.nodes.recruiter_finder import recruiter_finder
from app.graph.nodes.writer import writer
from app.graph.state import Critique, EmailDraft, JobInfo, Link, RecruiterResult


def _job() -> JobInfo:
    return JobInfo(company="Acme", title="AI Engineer", key_requirements=["LangGraph"])


# --- JD Analyzer -------------------------------------------------------------
def test_jd_analyzer_extracts_structured_job(mock_llm):
    mock_llm.add_structured(JobInfo, _job())
    out = jd_analyzer({"page_text": "Acme is hiring an AI Engineer …"})
    assert out["job"].company == "Acme"
    assert "recruiter" not in out  # no email in the page -> no recruiter shortcut


def test_jd_analyzer_picks_up_email_from_posting(mock_llm):
    """Email in the posting text -> recruiter is filled deterministically (regex),
    which lets the supervisor skip the web-search step entirely."""
    mock_llm.add_structured(JobInfo, _job())
    page = "Acme AI Engineer role. Contact: jane@acme.com"
    out = jd_analyzer({"page_text": page})
    assert out["recruiter"].email == "jane@acme.com"
    assert out["recruiter"].source == "jd"


# --- Recruiter Finder (ReAct loop) ------------------------------------------
def test_recruiter_finder_terminates_on_no_tool_call(mock_llm, fake_web_search):
    """If the first LLM step returns no tool_calls, the loop breaks immediately."""
    fake_web_search("would not be used")
    mock_llm.add_tool_reply(AIMessage(content="nothing to search"))
    mock_llm.add_structured(
        RecruiterResult,
        RecruiterResult(email=None, candidate_urls=[], source="none"),
    )
    out = recruiter_finder({"job": _job()})
    assert out["recruiter"].source == "none"


def test_recruiter_finder_iterates_then_extracts(mock_llm, fake_web_search):
    fake_web_search("RESULT: jane@acme.com is the AI talent lead")
    mock_llm.add_tool_reply(
        AIMessage(
            content="searching",
            tool_calls=[
                {
                    "name": "web_search",
                    "args": {"query": "acme recruiter ai"},
                    "id": "c1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="found it"),  # no tool_calls -> break
    )
    mock_llm.add_structured(
        RecruiterResult,
        RecruiterResult(email="jane@acme.com", candidate_urls=[], source="search"),
    )
    out = recruiter_finder({"job": _job()})
    assert out["recruiter"].email == "jane@acme.com"


def test_recruiter_finder_hits_max_searches_and_degrades(
    mock_llm, fake_web_search, monkeypatch
):
    """When the budget is exhausted, the node degrades to candidate URLs."""
    monkeypatch.setattr("app.config.MAX_SEARCHES", 2)
    fake_web_search("some search result")
    mock_llm.add_tool_reply(
        AIMessage(
            content="r1",
            tool_calls=[
                {"name": "web_search", "args": {"query": "q1"},
                 "id": "c1", "type": "tool_call"}
            ],
        ),
        AIMessage(
            content="r2",
            tool_calls=[
                {"name": "web_search", "args": {"query": "q2"},
                 "id": "c2", "type": "tool_call"}
            ],
        ),
    )
    mock_llm.add_structured(
        RecruiterResult,
        RecruiterResult(
            email=None,
            candidate_urls=[Link(title="Acme careers", url="https://acme.com/careers")],
            source="search",
        ),
    )
    out = recruiter_finder({"job": _job()})
    assert out["recruiter"].email is None
    assert out["recruiter"].candidate_urls[0].url == "https://acme.com/careers"


# --- Writer (dual mode) ------------------------------------------------------
def test_writer_generate_mode(mock_llm):
    """No draft in state -> writer infers generate mode."""
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="Hi", body="body"))
    out = writer({"job": _job(), "resume_text": "RESUME"})
    assert out["draft"].subject == "Hi"
    # generate does NOT touch revision_count (supervisor already reset it).
    assert "revision_count" not in out


def test_writer_critic_driven_revise_increments_revision_count(mock_llm):
    """Draft + failing critique -> critic-driven revise -> increment counter."""
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="revised", body="body"))
    failing = Critique(
        specificity=2, tone=3, no_placeholders=True, length_ok=True,
        no_hallucination=True, passed=False, feedback="add specifics",
    )
    out = writer({
        "job": _job(), "resume_text": "R",
        "draft": EmailDraft(subject="old", body="old"),
        "critique": failing, "revision_count": 0, "user_message": "",
    })
    assert out["revision_count"] == 1
    assert "user_message" not in out


def test_writer_user_driven_revise_clears_user_message(mock_llm):
    """Draft + no critique + user_message -> user-driven revise. Consumes the
    user_message so the supervisor stops; does NOT eat the critic loop budget."""
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="shorter", body="b"))
    out = writer({
        "job": _job(), "resume_text": "R",
        "draft": EmailDraft(subject="old", body="old"),
        "critique": None, "revision_count": 0, "user_message": "make it shorter",
    })
    assert out["user_message"] == ""
    assert "revision_count" not in out


# --- Critic ------------------------------------------------------------------
def test_critic_returns_structured_critique(mock_llm):
    mock_llm.add_structured(
        Critique,
        Critique(specificity=5, tone=5, no_placeholders=True, length_ok=True,
                 no_hallucination=True, passed=True, feedback=""),
    )
    out = critic_node({
        "job": _job(), "resume_text": "R",
        "draft": EmailDraft(subject="s", body="b"),
    })
    assert out["critique"].passed is True
