"""Shared state for the outreach multi-agent graph.

The graph state is a *business blackboard*, not an LLM transcript: it holds
structured results, never raw chat messages. Each agentic node manages its own
internal message loop and writes only structured output back here.
"""
from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Structured sub-models. Also used directly as LLM structured-output schemas,
# so the field descriptions double as instructions to the model.
# --------------------------------------------------------------------------
class JobInfo(BaseModel):
    """Structured job information extracted from a raw job posting."""

    company: str = Field(description="Hiring company name.")
    title: str = Field(description="Job title.")
    seniority: Optional[str] = Field(
        default=None,
        description='Seniority level, e.g. "New Grad", "Senior". Null if unclear.',
    )
    key_requirements: list[str] = Field(
        default_factory=list,
        description="The most important skills/requirements an applicant should address.",
    )


class Link(BaseModel):
    title: str
    url: str


class RecruiterResult(BaseModel):
    """Outcome of recruiter-contact discovery."""

    email: Optional[str] = Field(
        default=None, description="Recruiter email address if found, else null."
    )
    candidate_urls: list[Link] = Field(
        default_factory=list,
        description="Fallback contact pages / recruiter profiles when no direct email is found.",
    )
    source: Literal["jd", "search", "none"] = Field(
        description='"jd" if the email came from the posting text, "search" from '
        'web search, "none" if nothing was found.'
    )


class EmailDraft(BaseModel):
    subject: str = Field(description="Email subject line.")
    body: str = Field(description="Plain-text email body, no markdown.")


class Critique(BaseModel):
    """Rubric-based evaluation of an outreach email draft."""

    specificity: int = Field(
        description="1-5: does the email cite concrete resume<->JD matches rather "
        "than generic claims?"
    )
    tone: int = Field(description="1-5: professional and warm, not sycophantic.")
    no_placeholders: bool = Field(
        description="True if the draft has no unfilled placeholders like [Company]."
    )
    length_ok: bool = Field(
        description="True if the body length is within the expected word range."
    )
    no_hallucination: bool = Field(
        description="True if the draft makes no claims unsupported by the resume."
    )
    passed: bool = Field(description="Overall pass/fail against the rubric threshold.")
    feedback: str = Field(
        description="Concrete, actionable revision notes for the writer. Empty when passed."
    )


# --------------------------------------------------------------------------
# Graph state
# --------------------------------------------------------------------------
class OutreachState(TypedDict, total=False):
    """Blackboard passed between graph nodes.

    total=False: every field is optional, so partial inputs (first request vs.
    follow-up) and partial node updates merge cleanly.
    """

    # ---- inputs ----
    resume_text: str          # applicant resume, plain text
    page_text: str            # raw job-posting page text
    user_message: str         # user's chat feedback this turn; "" on first generate

    # ---- working state ----
    job: Optional[JobInfo]
    recruiter: Optional[RecruiterResult]
    draft: Optional[EmailDraft]
    # Writer's mode (generate vs critic-driven vs user-driven revise) is inferred
    # from state — not a separate field. The critic edge returns to the writer
    # directly and would have no chance to re-set such a field.
    critique: Optional[Critique]
    revision_count: int       # loop guard for the Writer<->Critic reflection loop

    # ---- control ----
    next: str                 # Supervisor's routing decision
    status: Literal["running", "done", "error"]
    error: Optional[str]
