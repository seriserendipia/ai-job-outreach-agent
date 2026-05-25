// Content script — auto-injected by Chrome on linkedin.com/jobs/* (see
// manifest content_scripts.matches). Silently monitors the LinkedIn DOM and
// writes the captured JD into chrome.storage so the side panel can render it
// the moment the user clicks the toolbar icon.
//
// No DOM injection on the page itself — the side panel (chrome.sidePanel)
// is browser-managed, so we don't need (or want) an overlay iframe here.
(function () {
  function extractJobText() {
    const node =
      document.querySelector("#job-details") ||
      document.querySelector(".jobs-description__content") ||
      document.querySelector(".jobs-description-content__text") ||
      document.querySelector(".jobs-box__html-content") ||
      document.querySelector("main");
    const text = (node ? node.innerText : document.body.innerText) || "";
    return text.replace(/\n{3,}/g, "\n\n").trim().slice(0, 12000);
  }

  function firstNonEmpty(selectors) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      const txt = el && el.innerText ? el.innerText.trim() : "";
      if (txt) return txt;
    }
    return "";
  }

  function extractJobInfo() {
    return {
      title: firstNonEmpty([
        ".job-details-jobs-unified-top-card__job-title h1 a",
        ".job-details-jobs-unified-top-card__job-title h1",
        ".job-details-jobs-unified-top-card__job-title",
        "h1.jobs-unified-top-card__job-title",
      ]),
      company: firstNonEmpty([
        ".job-details-jobs-unified-top-card__company-name a",
        ".job-details-jobs-unified-top-card__company-name",
        ".jobs-unified-top-card__company-name a",
        ".jobs-unified-top-card__company-name",
      ]),
    };
  }

  let lastFingerprint = "";
  function pushPage() {
    const text = extractJobText();
    const info = extractJobInfo();
    const fingerprint = info.company + "|" + info.title + "|" + text.length;
    if (fingerprint === lastFingerprint) return;
    lastFingerprint = fingerprint;
    chrome.storage.local.set({
      ajoaPageData: {
        url: location.href,
        text: text,
        company: info.company,
        title: info.title,
        capturedAt: Date.now(),
      },
    });
  }

  // 1s polling is more reliable than a MutationObserver against LinkedIn's
  // continuous DOM churn (observer-debounce can starve, never pushing the
  // final state). Idle ticks are essentially free thanks to the fingerprint
  // short-circuit above.
  setInterval(pushPage, 1000);
  setTimeout(pushPage, 800);
})();
