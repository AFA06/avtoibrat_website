/* Opens a test in full screen the moment the student starts it.
   Browsers only allow full screen from a click, and full screen is dropped when the page navigates,
   so the test is loaded in a full-screen frame on top of the panel instead of replacing the page.
   When the test finishes and a normal panel page loads inside the frame, the top window takes over. */
(function () {
  "use strict";

  // Inside the frame: any page other than the test itself (the result) belongs in the top window.
  if (window.top !== window.self) {
    try {
      if (window.frameElement && window.frameElement.id === "examLaunchFrame" && !/\/test-session\//.test(location.pathname)) {
        window.top.location.replace(location.href);
      }
    } catch (e) { /* cross-origin: leave as is */ }
    return;
  }

  const START = /\/(marafon|mavzu|ohshash|saqlangan|shablon-test|real_imtihon)\/start\/|\/test-session\/\d+\/?$/;
  let layer = null;

  function open(openIt) {
    if (layer || !document.fullscreenEnabled) return false;
    layer = document.createElement("div");
    layer.id = "examLaunchLayer";
    layer.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:#0b1220;";
    const frame = document.createElement("iframe");
    frame.id = "examLaunchFrame";
    frame.name = "examLaunchFrame";
    frame.setAttribute("allow", "fullscreen");
    frame.style.cssText = "width:100%;height:100%;border:0;display:block;";
    layer.appendChild(frame);
    document.body.appendChild(layer);
    layer.requestFullscreen().catch(() => {});
    openIt(frame);
    return true;
  }

  function close() {
    if (layer) layer.remove();
    layer = null;
  }
  document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement) close(); });

  window.avtoExamLaunch = (url) => open((frame) => { frame.src = url; });

  document.addEventListener("click", (event) => {
    const link = event.target.closest && event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.target && link.target !== "_self") return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !START.test(url.pathname)) return;
    if (window.avtoExamLaunch(url.href)) event.preventDefault();
  });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form || event.defaultPrevented || !START.test(new URL(form.action, location.href).pathname)) return;
    open((frame) => { form.target = frame.name; });
  });
})();
