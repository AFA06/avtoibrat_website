/* Opens a test in full screen the moment the student starts it.
   Browsers only allow full screen from a click, and full screen is dropped when the page navigates,
   so the test is loaded in a full-screen frame on top of the panel instead of replacing the page.
   When the test finishes and a normal panel page loads inside the frame, the top window takes over. */
(function () {
  "use strict";

  // Inside the frame: any panel page (e.g. the season road with its result) belongs in the top window.
  // Loaded first in <head>, so stopping here keeps the page's own scripts from running inside the frame.
  if (window.top !== window.self) {
    try {
      if (window.frameElement && window.frameElement.id === "examLaunchFrame" && !/\/test-session\//.test(location.pathname)) {
        window.top.location.replace(location.href);
        window.stop();
      }
    } catch (e) { /* cross-origin: leave as is */ }
    return;
  }

  const START = /\/(marafon|mavzu|ohshash|saqlangan|shablon-test|real_imtihon)\/start\/|\/test-session\/\d+\/?$/;
  let layer = null;
  let fullscreenChanging = false;
  let expanded = true;

  function dismissStartDialog() {
    // Its backdrop otherwise keeps blurring/blocking the exposed app chrome.
    document.querySelectorAll(".popup").forEach((popup) => {
      popup.style.display = "none";
      popup.setAttribute("aria-hidden", "true");
    });
    document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  }

  function layoutExam() {
    if (!layer) return;
    if (expanded) {
      layer.style.inset = "0";
      return;
    }
    // Dock inside the panel instead of continuing to cover its sidebar/header.
    dismissStartDialog();
    const sidebar = document.querySelector(".left-sidebar");
    const header = document.querySelector(".topbar .navbar-custom") || document.querySelector(".topbar");
    const left = innerWidth >= 992 && sidebar ? Math.max(0, sidebar.getBoundingClientRect().right) : 0;
    const top = header ? Math.max(0, header.getBoundingClientRect().bottom) : 0;
    layer.style.inset = `${top}px 0 0 ${left}px`;
  }

  // One owner for both the button and L: keep the iframe mounted while
  // Chrome leaves fullscreen, preserving the question, answers and timer.
  window.avtoExamToggleFullscreen = async () => {
    if (!layer || fullscreenChanging) return;
    fullscreenChanging = true;
    try {
      if (expanded) {
        expanded = false;
        if (document.fullscreenElement) await document.exitFullscreen();
      } else {
        expanded = true;
        if (document.fullscreenEnabled) await layer.requestFullscreen();
      }
    } catch (error) {
      console.warn("Exam fullscreen toggle failed", error);
    } finally {
      layoutExam();
      fullscreenChanging = false;
    }
  };

  function open(openIt) {
    if (layer) return false;
    expanded = true;
    layer = document.createElement("div");
    layer.id = "examLaunchLayer";
    layer.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:#0b1220;";
    const frame = document.createElement("iframe");
    frame.id = "examLaunchFrame";
    frame.name = "examLaunchFrame";
    frame.title = "AvtoIbrat — Test";
    frame.setAttribute("allow", "fullscreen");
    frame.style.cssText = "width:100%;height:100%;border:0;display:block;";
    layer.appendChild(frame);
    document.body.appendChild(layer);
    // The test has its own question-language switch; hide the panel's site-language menu meanwhile.
    document.documentElement.classList.add("exam-active");
    dismissStartDialog();
    if (document.fullscreenEnabled) layer.requestFullscreen().catch(() => {});
    openIt(frame);
    return true;
  }

  // Leaving fullscreen (the exam's L shortcut or the browser's fullscreen key)
  // should reveal Chrome's tabs while keeping the active exam iframe alive.
  // The iframe is removed naturally when the exam finishes and navigates the
  // top window back to the dashboard.

  window.avtoExamLaunch = (url) => open((frame) => { frame.src = url; });

  document.addEventListener("fullscreenchange", () => {
    if (layer && !document.fullscreenElement) {
      expanded = false;
      layoutExam();
    }
  });
  window.addEventListener("resize", layoutExam);
  // Sidebar collapse animates its width; track its final position too.
  document.addEventListener("transitionend", (event) => {
    if (event.target.matches(".left-sidebar")) layoutExam();
  });

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
