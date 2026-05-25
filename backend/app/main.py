"""FastAPI server exposing the outreach graph and the Gmail send helper.

  POST /compose  — run the multi-agent graph (generate or revise an email)
  POST /send     — send an email via Gmail (plain operation, not in the graph)
"""
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph.graph import graph
from app.tools.gmail import send_email

app = FastAPI(title="ai-job-outreach-agent")

# Open CORS: the only client is a Chrome extension (chrome-extension:// origin),
# and the server holds no secrets of its own. Tighten before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# /compose
# --------------------------------------------------------------------------
class ComposeRequest(BaseModel):
    thread_id: str                 # one job posting == one thread
    resume_text: str = ""          # required on the first turn
    page_text: str = ""            # required on the first turn
    user_message: str = ""         # revision feedback on follow-up turns


class ComposeResponse(BaseModel):
    subject: str
    body: str
    company: str | None = None
    title: str | None = None
    recruiter_email: str | None = None
    recruiter_urls: list[dict] = []
    critique: dict | None = None


@app.post("/compose", response_model=ComposeResponse)
def compose(req: ComposeRequest):
    """Run the graph. State is keyed by thread_id, so a follow-up turn resumes the
    same job context and only re-runs what is needed (typically just writer+critic)."""
    cfg = {"configurable": {"thread_id": req.thread_id}}
    inputs: dict = {"user_message": req.user_message}
    # resume/page only matter on the first turn; on follow-ups the checkpointer
    # already has them, so pass them only when provided.
    if req.resume_text:
        inputs["resume_text"] = req.resume_text
    if req.page_text:
        inputs["page_text"] = req.page_text

    try:
        result = graph.invoke(inputs, config=cfg)
    except Exception as e:  # noqa: BLE001 — surface any graph failure to the client
        raise HTTPException(status_code=500, detail=f"Graph error: {e}")

    draft = result.get("draft")
    job = result.get("job")
    recruiter = result.get("recruiter")
    critique = result.get("critique")
    return ComposeResponse(
        subject=draft.subject if draft else "",
        body=draft.body if draft else "",
        company=job.company if job else None,
        title=job.title if job else None,
        recruiter_email=recruiter.email if recruiter else None,
        recruiter_urls=(
            [link.model_dump() for link in recruiter.candidate_urls]
            if recruiter
            else []
        ),
        critique=critique.model_dump() if critique else None,
    )


# --------------------------------------------------------------------------
# /send
# --------------------------------------------------------------------------
class SendRequest(BaseModel):
    to: str
    subject: str
    body: str
    access_token: str              # Google OAuth token from the extension


@app.post("/send")
async def send(req: SendRequest):
    try:
        result = await send_email(req.to, req.subject, req.body, req.access_token)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502, detail=f"Gmail API error: {e.response.text}"
        )
    return {"success": True, "message_id": result.get("id")}


@app.get("/health")
def health():
    return {"status": "ok"}
