/* Exam and panel share the same light/dark preference.
   Same default as the panel: light unless dark was chosen.
   Loaded in <head> without defer so the first paint already has the right theme. */
(function () {
  "use strict";
  const KEY = "avtoibrat.theme";
  const root = document.documentElement;

  let toggle;

  function apply(theme) {
    const dark = theme === "dark";
    root.setAttribute("data-theme", dark ? "dark" : "light");
    if (toggle) {
      toggle.setAttribute("aria-pressed", String(dark));
      toggle.title = dark ? toggle.dataset.toLight : toggle.dataset.toDark;
    }
  }

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
  window.addEventListener("storage", (e) => {
    if (e.key === KEY && (e.newValue === "dark" || e.newValue === "light")) apply(e.newValue);
  });

  document.addEventListener("DOMContentLoaded", () => {
    toggle = document.getElementById("examThemeToggle");
    if (!toggle) return;
    apply(root.getAttribute("data-theme"));
    toggle.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      try {
        window.localStorage.setItem(KEY, next);
      } catch (error) { /* Storage is blocked. Keep the choice for this exam. */ }
    });
  });
})();
