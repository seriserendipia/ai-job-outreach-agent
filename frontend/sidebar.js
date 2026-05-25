// Sidebar UI logic: talks to the backend graph and the Gmail send endpoint.
const BACKEND = "http://localhost:8000";

let pageData = { url: "", text: "", company: "", title: "" };
let resumeText = "";
// Source of truth for the AI-generated email. The preview DOM is derived from
// this; Send reads from this — so users cannot accidentally edit the AI's
// output, they must ask the AI to revise it.
let currentEmail = { subject: "", body: "" };

const $ = (id) => document.getElementById(id);

// ============================================================================
// Page bridge (content script -> chrome.storage -> here)
// ============================================================================
// With chrome.sidePanel the sidebar is no longer iframed inside the page, so
// postMessage doesn't apply. The content script writes the captured JD into
// chrome.storage.local under `ajoaPageData`; we read it on mount and watch
// chrome.storage.onChanged for updates.
function adoptPageData(d) {
  if (!d) return;
  pageData = {
    url: d.url || "",
    text: d.text || "",
    company: d.company || "",
    title: d.title || "",
  };
  renderJobCard();
}

chrome.storage.local.get("ajoaPageData", (r) => adoptPageData(r.ajoaPageData));
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.ajoaPageData) {
    adoptPageData(changes.ajoaPageData.newValue);
  }
});

// Persist the last AI-generated email so opening / re-opening the side panel
// restores the prior state. The native side panel is a fresh document each
// open; without this, the user would lose their draft every time they closed
// and reopened it.
chrome.storage.local.get("ajoaCurrentEmail", (r) => {
  if (r.ajoaCurrentEmail) applyResult(r.ajoaCurrentEmail);
});

function renderJobCard() {
  const titleEl = $("job-title");
  const companyEl = $("job-company");
  const previewEl = $("jd-preview");

  if (pageData.title) {
    titleEl.textContent = pageData.title;
  } else if (!pageData.text) {
    titleEl.textContent = "Waiting for the job posting to load…";
  } else {
    titleEl.textContent = "Job posting captured";
  }

  if (pageData.company) {
    companyEl.textContent = "at " + pageData.company;
    companyEl.classList.remove("hidden");
  } else {
    companyEl.classList.add("hidden");
  }

  if (pageData.text) {
    previewEl.textContent =
      pageData.text.slice(0, 1500) + (pageData.text.length > 1500 ? "\n…" : "");
    previewEl.classList.remove("hidden");
  } else {
    previewEl.classList.add("hidden");
  }
}

// (No on-mount request needed — content script writes to chrome.storage
// continuously; we already read the latest on mount above.)

// ============================================================================
// Resume — upload OR paste, single source of truth
// ============================================================================
chrome.storage.local.get(["resume", "resumeName"], (r) => {
  if (r && r.resume) {
    resumeText = r.resume;
    renderResumeStatus(r.resumeName || "(saved)");
    // If they pasted before, keep the textarea visible with the content.
    if (r.resumeName === "(pasted)") {
      $("resume-paste").value = r.resume;
      $("resume-paste").classList.remove("hidden");
    }
  }
});

$("resume-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    resumeText = String(reader.result || "");
    chrome.storage.local.set({ resume: resumeText, resumeName: file.name });
    renderResumeStatus(file.name);
    $("resume-paste").classList.add("hidden");
  };
  reader.readAsText(file);
});

$("paste-toggle").addEventListener("click", (e) => {
  e.preventDefault();
  $("resume-paste").classList.toggle("hidden");
  if (!$("resume-paste").classList.contains("hidden")) {
    $("resume-paste").focus();
  }
});

$("resume-paste").addEventListener("input", () => {
  resumeText = $("resume-paste").value;
  chrome.storage.local.set({ resume: resumeText, resumeName: "(pasted)" });
  renderResumeStatus("(pasted)");
});

function renderResumeStatus(label) {
  const uploadLabel = $("upload-label");
  const pasteToggle = $("paste-toggle");
  const pasteDivider = $("paste-divider");
  const clearBtn = $("clear-resume");

  if (!resumeText.trim()) {
    uploadLabel.textContent = "📄 Upload .txt";
    pasteToggle.classList.remove("hidden");
    pasteDivider.classList.remove("hidden");
    clearBtn.classList.add("hidden");
  } else {
    // Filled: the label itself becomes the filename. Clicking it still opens
    // the file picker (label-for=resume-file), so it doubles as "replace".
    uploadLabel.textContent = "📄 " + label;
    pasteToggle.classList.add("hidden");
    pasteDivider.classList.add("hidden");
    clearBtn.classList.remove("hidden");
  }
}

function clearResume() {
  resumeText = "";
  chrome.storage.local.remove(["resume", "resumeName"]);
  $("resume-paste").value = "";
  $("resume-paste").classList.add("hidden");
  $("resume-file").value = "";
  renderResumeStatus("");
}

$("clear-resume").addEventListener("click", (e) => {
  e.preventDefault();
  clearResume();
});

// ============================================================================
// Helpers
// ============================================================================
function threadId() {
  return pageData.url || "default-thread";
}

function setStatus(msg, isError) {
  const el = $("status");
  el.textContent = msg || "";
  el.className = "status" + (isError ? " error" : "");
}

function setBusy(busy, msg) {
  $("generate-btn").disabled = busy;
  $("revise-btn").disabled = busy;
  $("send-btn").disabled = busy;
  if (msg !== undefined) setStatus(msg);
}

// ============================================================================
// Compose (generate or revise)
// ============================================================================
async function compose(userMessage) {
  if (!resumeText.trim()) {
    setStatus("Add your resume first.", true);
    return;
  }
  if (!userMessage && !pageData.text) {
    setStatus("Job posting not captured yet — give it a moment and try again.", true);
    return;
  }

  setBusy(true, userMessage ? "Revising…" : "Running agents…");
  try {
    const res = await fetch(BACKEND + "/compose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: threadId(),
        resume_text: resumeText,
        page_text: pageData.text,
        user_message: userMessage || "",
      }),
    });
    if (!res.ok) {
      throw new Error("compose failed (" + res.status + "): " + (await res.text()));
    }
    applyResult(await res.json());
    setStatus("");
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    setBusy(false);
  }
}

function applyResult(data) {
  currentEmail = { subject: data.subject || "", body: data.body || "" };
  chrome.storage.local.set({ ajoaCurrentEmail: data });
  renderEmailPreview();
  $("email-card").classList.remove("hidden");
  $("send-card").classList.remove("hidden");

  // The LLM-parsed title/company are usually cleaner than the DOM scrape.
  if (data.title) $("job-title").textContent = data.title;
  if (data.company) {
    $("job-company").textContent = "at " + data.company;
    $("job-company").classList.remove("hidden");
  }

  if (data.recruiter_email) {
    $("to").value = data.recruiter_email;
    $("recruiter-hint").textContent = "Recruiter email found automatically.";
  } else if (data.recruiter_urls && data.recruiter_urls.length) {
    $("recruiter-hint").innerHTML =
      "No direct email. Try: " +
      data.recruiter_urls
        .map(
          (u) =>
            '<a href="' +
            u.url +
            '" target="_blank" rel="noopener">' +
            (u.title || u.url) +
            "</a>"
        )
        .join(" · ");
  } else {
    $("recruiter-hint").textContent =
      "No recruiter contact found — enter one manually.";
  }

  if (data.critique) {
    const c = data.critique;
    $("critique").textContent =
      "Critic: " +
      (c.passed ? "passed" : "needs work") +
      " · specificity " +
      c.specificity +
      "/5 · tone " +
      c.tone +
      "/5";
    $("critique").className = "critique " + (c.passed ? "ok" : "warn");
    $("critique").classList.remove("hidden");
  }
}

// ============================================================================
// Send via Gmail
// ============================================================================
function getGmailToken() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: "AJOA_GET_TOKEN" }, (resp) => {
      if (chrome.runtime.lastError) {
        return reject(new Error(chrome.runtime.lastError.message));
      }
      if (!resp || !resp.ok) {
        return reject(new Error((resp && resp.error) || "authorization failed"));
      }
      resolve(resp.token);
    });
  });
}

function renderEmailPreview() {
  const el = $("email-preview");
  el.innerHTML = "";
  // Before generation: read-only placeholder.
  if (!currentEmail.subject && !currentEmail.body) {
    const ph = document.createElement("span");
    ph.className = "email-placeholder";
    ph.textContent = "Generated email will appear here.";
    el.appendChild(ph);
    return;
  }
  // After generation: editable input + textarea, styled to look like a
  // preview. Keeps the AI-authorship feel but lets the user tweak a word
  // without going back through a Revise round-trip.
  const subj = document.createElement("input");
  subj.type = "text";
  subj.className = "email-subject-input";
  subj.value = currentEmail.subject;
  subj.addEventListener("input", () => {
    currentEmail.subject = subj.value;
  });

  const body = document.createElement("textarea");
  body.className = "email-body-input";
  body.value = currentEmail.body;
  body.addEventListener("input", () => {
    currentEmail.body = body.value;
  });

  el.appendChild(subj);
  el.appendChild(body);
}

async function send() {
  const to = $("to").value.trim();
  if (!to) {
    setStatus("Enter a recipient email.", true);
    return;
  }
  if (!currentEmail.subject || !currentEmail.body) {
    setStatus("Generate an email first.", true);
    return;
  }
  setBusy(true, "Authorizing Gmail…");
  try {
    const token = await getGmailToken();
    setStatus("Sending…");
    const res = await fetch(BACKEND + "/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to: to,
        subject: currentEmail.subject,
        body: currentEmail.body,
        access_token: token,
      }),
    });
    if (!res.ok) {
      throw new Error("send failed (" + res.status + "): " + (await res.text()));
    }
    setStatus("Email sent ✓");
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    setBusy(false);
  }
}

// ============================================================================
// Wire up
// ============================================================================
$("generate-btn").addEventListener("click", () => compose(""));
$("revise-btn").addEventListener("click", () => {
  const fb = $("feedback").value.trim();
  if (!fb) {
    setStatus("Type what to change.", true);
    return;
  }
  compose(fb).then(() => {
    $("feedback").value = "";
  });
});
$("send-btn").addEventListener("click", send);

renderJobCard();
