"""JD Analyzer node — a plain worker, not an agent.

Extracts structured JobInfo from the raw posting. Also opportunistically picks up
a recruiter email if one is printed directly in the posting text, which lets the
Supervisor skip the web-search step entirely.
"""
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.prompts import JD_ANALYZER_SYSTEM
from app.graph.state import JobInfo, OutreachState, RecruiterResult
from app.llm import make_llm

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def jd_analyzer(state: OutreachState) -> dict:
    page_text = state.get("page_text", "")

    llm = make_llm(temperature=0)
    job: JobInfo = llm.with_structured_output(JobInfo).invoke(
        [
            SystemMessage(content=JD_ANALYZER_SYSTEM),
            HumanMessage(content=page_text),
        ]
    )
    update: dict = {"job": job}

    # Deterministic: if an email is literally in the posting, use it directly.
    match = _EMAIL_RE.search(page_text)
    if match:
        update["recruiter"] = RecruiterResult(
            email=match.group(0), candidate_urls=[], source="jd"
        )
    return update
