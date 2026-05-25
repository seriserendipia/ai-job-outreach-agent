# e2e

Real-browser integration tests for the Chrome extension. Loads the unpacked
extension into a real Chrome via Playwright, navigates to a real LinkedIn job
page using the persistent profile that already holds a logged-in session, and
asserts the sidebar injected and captured the JD correctly.

Unlike the unit tests in `backend/tests/`, this needs:

- the Xvfb / x11vnc / noVNC stack up — `~/bin/browser-up.sh`
- no interactive Chrome holding the profile lock — `~/bin/chrome-down.sh` if needed
- the extension installed once via `chrome://extensions` "Load unpacked" in
  the persistent profile (see `~/BROWSER_STACK.md`)
- a logged-in LinkedIn session in `~/.chrome-profile`

Run:

```bash
cd backend && source .venv/bin/activate
pytest ../e2e/
```

A `pytest` from the repo root (or `pytest backend/tests`) does NOT run these —
`backend/pyproject.toml` restricts default discovery to `backend/tests/`, so
the e2e suite only runs when you ask for it.

The session leaves a screenshot at `/tmp/e2e-sidebar.png`.
