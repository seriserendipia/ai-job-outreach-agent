"""FastAPI endpoint tests. Backend logic is fully mocked."""
from langchain_core.messages import AIMessage

from app.graph.state import Critique, EmailDraft, JobInfo, RecruiterResult


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_compose_returns_email_and_recruiter(client, mock_llm, fake_web_search):
    fake_web_search("result")
    mock_llm.add_structured(
        JobInfo,
        JobInfo(company="Acme", title="AI Engineer", key_requirements=["LangGraph"]),
    )
    mock_llm.add_tool_reply(AIMessage(content="done"))
    mock_llm.add_structured(
        RecruiterResult,
        RecruiterResult(email="r@acme.com", candidate_urls=[], source="search"),
    )
    mock_llm.add_structured(EmailDraft, EmailDraft(subject="Hi Acme", body="…"))
    mock_llm.add_structured(
        Critique,
        Critique(specificity=5, tone=5, no_placeholders=True, length_ok=True,
                 no_hallucination=True, passed=True, feedback=""),
    )

    res = client.post(
        "/compose",
        json={"thread_id": "api-test-1", "resume_text": "R",
              "page_text": "P", "user_message": ""},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["subject"] == "Hi Acme"
    assert data["company"] == "Acme"
    assert data["title"] == "AI Engineer"
    assert data["recruiter_email"] == "r@acme.com"
    assert data["critique"]["passed"] is True


def test_send_calls_gmail_helper(client, monkeypatch):
    captured: dict = {}

    async def fake_send(to, subject, body, access_token):
        captured.update(
            {"to": to, "subject": subject, "body": body, "token": access_token}
        )
        return {"id": "msg-123"}

    monkeypatch.setattr("app.main.send_email", fake_send)

    res = client.post(
        "/send",
        json={"to": "jane@acme.com", "subject": "s", "body": "b", "access_token": "tok"},
    )
    assert res.status_code == 200
    assert res.json() == {"success": True, "message_id": "msg-123"}
    assert captured == {"to": "jane@acme.com", "subject": "s", "body": "b", "token": "tok"}
