"""Supervisor node — hierarchical delegation.

Re-evaluates the blackboard on every visit and dispatches to a specialist. It is
NOT a fixed pipeline: routing depends on what is already in state, so a follow-up
request (state resumed via the checkpointer) skips steps already completed.
"""
from app.graph.state import OutreachState


def supervisor(state: OutreachState) -> dict:
    job = state.get("job")
    recruiter = state.get("recruiter")
    draft = state.get("draft")
    user_message = (state.get("user_message") or "").strip()

    # Job not yet understood -> analyze the posting.
    if job is None:
        return {"next": "jd_analyzer", "status": "running"}

    # Recruiter contact unknown -> search. (If the posting contained an email,
    # jd_analyzer already filled `recruiter`, so this branch is skipped.)
    if recruiter is None:
        return {"next": "recruiter_finder", "status": "running"}

    # No draft yet -> first-time generation. Writer infers the mode from state
    # (draft is None == generate).
    if draft is None:
        return {"next": "writer", "revision_count": 0, "status": "running"}

    # A draft exists and the user asked for a change -> revise. Reset the
    # reflection-loop state so the critic gets a fresh budget.
    if user_message:
        return {
            "next": "writer",
            "critique": None,
            "revision_count": 0,
            "status": "running",
        }

    # Everything ready, nothing pending.
    return {"next": "END", "status": "done"}
