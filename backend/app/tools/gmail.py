"""Send an email through the Gmail API.

Not part of the agent graph: sending is a plain operation with no reasoning, so
it lives as a standalone helper called by the FastAPI /send endpoint.

The OAuth access token is supplied per-request by the Chrome extension
(obtained via chrome.identity). Nothing is stored server-side.
"""
import base64
from email.message import EmailMessage

import httpx

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _build_raw_message(to: str, subject: str, body: str) -> str:
    """Build a MIME message and encode it base64url, as the Gmail API expects."""
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


async def send_email(to: str, subject: str, body: str, access_token: str) -> dict:
    """Send an email as the authenticated user. Raises httpx.HTTPStatusError on failure."""
    raw = _build_raw_message(to, subject, body)
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            GMAIL_SEND_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )
    resp.raise_for_status()
    return resp.json()
