"""Pure-function tests for the routing logic.

The supervisor node and the critic-edge router are both pure: they look at the
state and return a routing decision. No LLM, no mocks needed.
"""
from app.graph.graph import _route_from_critic
from app.graph.nodes.supervisor import supervisor
from app.graph.state import Critique, EmailDraft, JobInfo, RecruiterResult

JOB = JobInfo(company="Acme", title="AI Engineer", key_requirements=[])
RECRUITER = RecruiterResult(email="r@acme.com", candidate_urls=[], source="jd")
DRAFT = EmailDraft(subject="s", body="b")
PASS = Critique(
    specificity=5, tone=5, no_placeholders=True, length_ok=True,
    no_hallucination=True, passed=True, feedback="",
)
FAIL = Critique(
    specificity=2, tone=3, no_placeholders=True, length_ok=True,
    no_hallucination=True, passed=False, feedback="add specifics",
)


# --- supervisor --------------------------------------------------------------
def test_routes_to_jd_analyzer_when_no_job():
    assert supervisor({})["next"] == "jd_analyzer"


def test_routes_to_recruiter_finder_when_job_but_no_recruiter():
    assert supervisor({"job": JOB})["next"] == "recruiter_finder"


def test_routes_to_writer_generate_when_no_draft():
    out = supervisor({"job": JOB, "recruiter": RECRUITER})
    assert out["next"] == "writer"
    assert out["revision_count"] == 0
    # Writer infers "generate" from `draft is None` — no mode field needed.


def test_routes_to_writer_revise_on_new_user_message():
    out = supervisor({
        "job": JOB, "recruiter": RECRUITER, "draft": DRAFT,
        "user_message": "make it shorter",
    })
    assert out["next"] == "writer"
    # Reset critique so the reflection loop gets a fresh budget for this revision.
    assert out["critique"] is None
    assert out["revision_count"] == 0


def test_routes_to_end_when_done():
    out = supervisor({
        "job": JOB, "recruiter": RECRUITER, "draft": DRAFT, "user_message": "",
    })
    assert out["next"] == "END"
    assert out["status"] == "done"


# --- critic edge router ------------------------------------------------------
def test_critic_router_loops_on_fail_within_budget():
    assert _route_from_critic({"critique": FAIL, "revision_count": 0}) == "writer"
    assert _route_from_critic({"critique": FAIL, "revision_count": 1}) == "writer"


def test_critic_router_stops_at_max_revisions():
    # Default MAX_REVISIONS is 2 — at the limit we give up and accept the draft.
    assert _route_from_critic({"critique": FAIL, "revision_count": 2}) == "supervisor"


def test_critic_router_stops_on_pass():
    assert _route_from_critic({"critique": PASS, "revision_count": 0}) == "supervisor"
