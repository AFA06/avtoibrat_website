/* Exam page follows the panel's light/dark choice (dashboard/theme-toggle.js), live.
   Same default as the panel: light unless dark was chosen.
   Loaded in <head> without defer so the first paint already has the right theme. */
(function () {
  "use strict";
  const KEY = "avtoibrat.theme";
  const root = document.documentElement;

  const apply = (theme) => root.setAttribute("data-theme", theme === "dark" ? "dark" : "light");

  // Launched inside the panel's iframe: mirror the parent page directly (same origin).
  function parentTheme() {
    try {
      return window.parent !== window ? window.parent.document.documentElement.getAttribute("data-theme") : null;
    } catch (error) {
      return null;
    }
  }

  function stored() {
    try { return window.localStorage.getItem(KEY); } catch (error) { return null; }
  }

  apply(parentTheme() || stored());

  // Panel toggle in the surrounding page (iframe) or another tab.
  try {
    if (window.parent !== window) {
      new MutationObserver(() => apply(parentTheme())).observe(window.parent.document.documentElement,
        { attributes: true, attributeFilter: ["data-theme"] });
    }
  } catch (error) { /* cross-origin parent: fall back to the storage event */ }
  window.addEventListener("storage", (e) => { if (e.key === KEY && e.newValue) apply(e.newValue); });
})();
