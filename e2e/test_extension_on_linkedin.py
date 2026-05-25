"""E2E: load the unpacked Chrome extension into a real Chrome, navigate to a
real LinkedIn job page so the content script populates chrome.storage with the
captured JD, then open the side panel page directly (chrome-extension://) and
assert it renders the captured JD.

The architecture moved to chrome.sidePanel (Chrome 114+). The sidebar is no
longer an iframe injected into the LinkedIn page — it's a browser-managed
side panel. Playwright can't drive the native side-panel chrome, so we navigate
to its HTML directly as an extension page, which exercises the same JS path.

See e2e/README.md for prerequisites.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
EXT_PATH = str(REPO_ROOT / "frontend")
PROFILE = "/home/agent/.chrome-profile"
LINKEDIN_URL = "https://www.linkedin.com/jobs/search/"
SCREENSHOT = "/usr/share/novnc/shots/e2e-sidebar.png"

STEALTH_INIT = (
    "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _find_extension_id(ctx) -> str:
    """Find our extension's ID via its background service worker, with a fall
    back to scanning the profile's Preferences (in case the worker hasn't
    registered yet)."""
    deadline = time.time() + 5.0
    while time.time() < deadline:
        for sw in ctx.service_workers:
            if sw.url.startswith("chrome-extension://") and sw.url.endswith(
                "/background.js"
            ):
                return sw.url.split("/")[2]
        time.sleep(0.3)

    prefs = Path(PROFILE) / "Default" / "Preferences"
    if prefs.exists():
        data = json.loads(prefs.read_text())
        for ext_id, info in data.get("extensions", {}).get("settings", {}).items():
            if "ai-job-outreach-agent/frontend" in (info.get("path") or ""):
                return ext_id
    raise RuntimeError(
        "Could not find the extension ID. Is the extension installed in the "
        "persistent profile? See ~/BROWSER_STACK.md for the one-time install step."
    )


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _require_xvfb():
    if subprocess.run(["pgrep", "-af", "Xvfb :99"]).returncode != 0:
        pytest.fail(
            "Xvfb :99 is not running. Bring up the stack first:\n"
            "    ~/bin/browser-up.sh"
        )


@pytest.fixture(scope="session")
def real_e2e():
    """One Chrome session, two tabs:
      - LinkedIn so the content script populates chrome.storage with the JD;
      - sidebar.html opened as an extension page to render the captured data.

    This exercises the full content-script <-> storage <-> sidebar pipeline,
    same as what happens when the user opens the native side panel.
    """
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            executable_path="/usr/bin/google-chrome",
            headless=False,
            env={**os.environ, "DISPLAY": ":99"},
            no_viewport=True,
            ignore_default_args=[
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
                "--disable-default-apps",
            ],
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
            ],
        )
        ctx.add_init_script(STEALTH_INIT)

        ext_id = _find_extension_id(ctx)
        print(f"\n→ extension id: {ext_id}")

        # Tab 1: LinkedIn — the content script runs here and writes to storage.
        linkedin = ctx.new_page()
        linkedin.set_viewport_size({"width": 1280, "height": 900})
        print(f"→ navigating to {LINKEDIN_URL} (watch in noVNC)")
        linkedin.goto(LINKEDIN_URL, wait_until="domcontentloaded", timeout=30_000)
        linkedin.wait_for_timeout(5_000)   # let the content script fire a couple polls

        # Tab 2: sidebar — opened directly as an extension page, sized to
        # roughly what Chrome gives the real native side panel (~400px wide),
        # so the final composite screenshot reflects the actual UX.
        sidebar = ctx.new_page()
        sidebar.set_viewport_size({"width": 400, "height": 900})
        sidebar.goto(
            f"chrome-extension://{ext_id}/sidebar.html",
            wait_until="domcontentloaded",
        )
        sidebar.wait_for_timeout(800)      # let onChanged or get-on-mount settle

        yield {"linkedin": linkedin, "sidebar": sidebar, "ctx": ctx}

        # --- final screenshot: simulate a generated email so the sidebar shows
        # the full populated UI (resume status + AI draft + send card), not
        # just the pre-generation state. Doesn't affect test assertions
        # (those already ran while the fixture was yielded).
        sidebar.evaluate(
            """
            () => {
              const ta = document.getElementById('resume-paste');
              ta.value = "Jordan Avery — Software Engineer\\n"
                       + "4 years backend & LLM features. Built a tool-calling "
                       + "document-extraction pipeline that lifted field-level "
                       + "accuracy from 82% to 96%. OSS: deskmate (600+ stars).";
              ta.classList.remove('hidden');
              ta.dispatchEvent(new Event('input'));

              window.applyResult({
                subject: "Backend engineer interested in the Acceleration Track role",
                body:
                  "Hi Netsurit team,\\n\\n" +
                  "Your Tier 2 Support Engineer posting on the AI Operations " +
                  "Acceleration Track caught my eye. The focus on managed " +
                  "services + AI ops matches what I built at Northwind: a " +
                  "document-extraction pipeline with a tool-calling validation " +
                  "loop that lifted accuracy from 82% to 96%. I also maintain " +
                  "\\"deskmate,\\" an open-source CLI that plans and executes " +
                  "shell tasks via a tool-calling agent (600+ stars).\\n\\n" +
                  "Would love a short conversation about how the Acceleration " +
                  "Track team measures impact on customer environments.\\n\\n" +
                  "Thanks,\\nJordan",
                recruiter_email: "talent@netsurit.com",
                recruiter_urls: [],
                critique: { passed: true, specificity: 5, tone: 4,
                            no_placeholders: true, length_ok: true,
                            no_hallucination: true, feedback: "" }
              });
            }
            """
        )
        sidebar.wait_for_timeout(400)

        # Tear down the hidden sidebar tab so the user only sees LinkedIn in
        # noVNC. They open the REAL native side panel via the toolbar icon —
        # that gives an honest screenshot of how the UX really looks, instead
        # of a misleading "sidebar.html as full-page tab" view.
        sidebar.close()
        linkedin.bring_to_front()

        if sys.stdin.isatty() and not os.getenv("E2E_NO_PAUSE"):
            print(
                "\n>>> Chrome left running on the LinkedIn tab."
                "\n>>> Open noVNC: http://localhost:6080/vnc.html?autoconnect=true&resize=scale"
                "\n>>> Click the 🧩 puzzle icon in Chrome's toolbar → click"
                "\n>>> 'AI Job Outreach Agent' to open the native side panel."
                "\n>>> (The seeded JD + simulated email draft will be there,"
                "\n>>>  restored from chrome.storage.)"
                "\n>>> Press Enter here when done — that closes Chrome.",
                flush=True,
            )
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass
        ctx.close()


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------
def test_storage_was_populated_by_content_script(real_e2e):
    """The content script (running on LinkedIn) should have written
    `ajoaPageData` into chrome.storage.local."""
    sidebar = real_e2e["sidebar"]
    data = sidebar.evaluate(
        "() => new Promise(res => chrome.storage.local.get('ajoaPageData', r => res(r.ajoaPageData)))"
    )
    assert data is not None, (
        "chrome.storage.local.ajoaPageData is missing — content script likely "
        "did not run or did not extract anything on the LinkedIn page"
    )
    assert (data.get("text") or "").strip(), "captured JD text is empty"


def test_sidebar_renders_jd_preview(real_e2e):
    sidebar = real_e2e["sidebar"]
    preview = sidebar.query_selector("#jd-preview")
    assert preview is not None
    cls = preview.get_attribute("class") or ""
    assert "hidden" not in cls, "#jd-preview stayed hidden — sidebar did not pick up storage"
    text = preview.inner_text().strip()
    assert len(text) > 500, (
        f"jd-preview text too short ({len(text)} chars): {text[:120]!r}"
    )


def test_sidebar_shows_title_and_company(real_e2e):
    sidebar = real_e2e["sidebar"]
    title = sidebar.query_selector("#job-title").inner_text().strip()
    company_el = sidebar.query_selector("#job-company")
    company = company_el.inner_text().strip() if company_el else ""
    assert title and "Waiting" not in title and "Reading" not in title, (
        f"job-title still shows placeholder: {title!r}"
    )
    assert company, "job-company is empty (company name not surfaced to sidebar)"
