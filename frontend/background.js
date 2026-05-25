// Service worker:
// 1) Make clicking the toolbar icon open the side panel (one click, browser-
//    managed sidebar; chrome.sidePanel cannot be auto-opened on page nav by
//    Chrome policy — it requires a user gesture).
// 2) Obtain a Google OAuth token for sending Gmail (sidebar messages us).

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((err) => console.error("setPanelBehavior:", err));
});

chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
  if (msg && msg.type === "AJOA_GET_TOKEN") {
    chrome.identity.getAuthToken({ interactive: true }, function (token) {
      if (chrome.runtime.lastError || !token) {
        sendResponse({
          ok: false,
          error:
            (chrome.runtime.lastError && chrome.runtime.lastError.message) ||
            "no token",
        });
      } else {
        sendResponse({ ok: true, token: token });
      }
    });
    return true;
  }
});
