"""Recruiter Finder node — the ReAct agent.

A hand-written reason -> act -> observe loop. The loop is intentionally
implemented here (rather than calling a prebuilt agent) so termination is
explicit: it is bounded by MAX_SEARCHES, and on exhaustion it degrades
gracefully to whatever candidate URLs were gathered.

The loop is encapsulated inside this single graph node: the search transcript is
an implementation detail of one capability and does not belong on the top-level
graph state.
"""
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app import config
from app.graph.prompts import RECRUITER_EXTRACT_SYSTEM, RECRUITER_REACT_SYSTEM
from app.graph.state import OutreachState, RecruiterResult
from app.llm import make_llm
from app.tools.web_search import web_search


def recruiter_finder(state: OutreachState) -> dict:
    job = state["job"]
    llm_with_tools = make_llm(temperature=0).bind_tools([web_search])

    messages = [
        SystemMessage(content=RECRUITER_REACT_SYSTEM),
        HumanMessage(
            content=f"Find a recruiter contact for the role: {job.title} at {job.company}."
        ),
    ]

    # --- ReAct loop: reason -> act -> observe, bounded by MAX_SEARCHES ---
    for _ in range(config.MAX_SEARCHES):
        ai = llm_with_tools.invoke(messages)          # reason
        messages.append(ai)
        if not ai.tool_calls:                         # model decided it is done
            break
        for call in ai.tool_calls:                    # act + observe
            observation = web_search.invoke(call["args"])
            messages.append(
                ToolMessage(content=observation, tool_call_id=call["id"])
            )

    # --- Extract a structured result from the search transcript ---
    extractor = make_llm(temperature=0).with_structured_output(RecruiterResult)
    result: RecruiterResult = extractor.invoke(
        messages + [HumanMessage(content=RECRUITER_EXTRACT_SYSTEM)]
    )
    return {"recruiter": result}
