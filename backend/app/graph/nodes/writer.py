"""Email Writer node — generate or revise, inferred from state.

The mode is read from the blackboard, not passed in:
  - no draft yet                            -> generate
  - draft + failing critique                -> critic-driven revise
                                                 (increments revision_count,
                                                  which guards the reflection loop)
  - draft + no critique + user_message      -> user-driven revise
                                                 (consumes user_message so the
                                                  supervisor will not re-trigger;
                                                  does NOT eat the loop budget)

Inferring from state — instead of carrying a `draft_mode` flag — means the
critic edge can return straight to the writer without having to re-set anything.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.prompts import WRITER_SYSTEM
from app.graph.state import EmailDraft, OutreachState
from app.llm import make_llm


def _context(state: OutreachState) -> str:
    job = state["job"]
    resume = state.get("resume_text", "")
    reqs = ", ".join(job.key_requirements) if job.key_requirements else "(none extracted)"
    return (
        f"Applicant resume:\n{resume}\n\n"
        f"Target role: {job.title} at {job.company}\n"
        f"Key requirements to address: {reqs}"
    )


def writer(state: OutreachState) -> dict:
    current = state.get("draft")
    critique = state.get("critique")
    user_message = (state.get("user_message") or "").strip()

    structured = make_llm(temperature=0.4).with_structured_output(EmailDraft)

    # --- generate ---
    if current is None:
        human = _context(state) + "\n\nWrite the outreach email."
        draft = structured.invoke(
            [SystemMessage(content=WRITER_SYSTEM), HumanMessage(content=human)]
        )
        return {"draft": draft}

    # --- revise (critic- or user-driven) ---
    critic_driven = critique is not None and not critique.passed
    if critic_driven:
        feedback = f"A reviewer flagged the current draft:\n{critique.feedback}"
    else:
        feedback = f"The user requested this change:\n{user_message}"

    human = (
        _context(state)
        + f"\n\nCurrent subject: {current.subject}"
        + f"\nCurrent body:\n{current.body}"
        + f"\n\n{feedback}"
        + "\n\nRewrite the email applying the feedback while keeping every hard constraint."
    )
    draft = structured.invoke(
        [SystemMessage(content=WRITER_SYSTEM), HumanMessage(content=human)]
    )

    if critic_driven:
        return {"draft": draft, "revision_count": state.get("revision_count", 0) + 1}
    # User-driven revision: consume user_message so the Supervisor stops here.
    return {"draft": draft, "user_message": ""}
