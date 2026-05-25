"""Email Critic node — self-reflection.

Scores the current draft against an explicit rubric (see CRITIC_SYSTEM) and
returns a structured Critique. The graph's conditional edge after this node
decides whether to loop back to the Writer or finish.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from app import config
from app.graph.prompts import CRITIC_SYSTEM
from app.graph.state import Critique, OutreachState
from app.llm import make_llm


def critic(state: OutreachState) -> dict:
    draft = state["draft"]
    job = state["job"]
    resume = state.get("resume_text", "")

    llm = make_llm(model=config.MODEL_CRITIC, temperature=0)
    human = (
        f"Applicant resume:\n{resume}\n\n"
        f"Target role: {job.title} at {job.company}\n\n"
        f"Email subject: {draft.subject}\n"
        f"Email body:\n{draft.body}"
    )
    critique: Critique = llm.with_structured_output(Critique).invoke(
        [SystemMessage(content=CRITIC_SYSTEM), HumanMessage(content=human)]
    )
    return {"critique": critique}
