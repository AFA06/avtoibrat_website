/* Light/dark switch: moon/sun button in the top bar, remembered per browser. */
(function () {
  "use strict";
  const KEY = "avtoibrat.theme";
  const root = document.documentElement;

  const current = () => (root.getAttribute("data-theme") === "dark" ? "dark" : "light");

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    const btn = document.getElementById("themeToggle");
    if (btn) {
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      btn.title = theme === "dark" ? btn.dataset.toLight : btn.dataset.toDark;
    }
  }

  function save(theme) {
    try { window.localStorage.setItem(KEY, theme); } catch (error) { /* storage blocked: choice lasts this page only */ }
  }

  function mount() {
    const bar = document.querySelector("ul.topbar-nav.float-end");
    if (!bar || document.getElementById("themeToggle")) return;
    const li = document.createElement("li");
    li.className = "d-flex align-items-center";
    li.innerHTML =
      '<button type="button" id="themeToggle" class="ai-theme-toggle" aria-label="Theme" ' +
      'data-to-dark="Tungi rejim" data-to-light="Kunduzgi rejim">' +
      '<i class="ti ti-moon"></i><i class="ti ti-sun"></i></button>';
    bar.insertBefore(li, bar.firstChild);
    const btn = li.firstChild;
    btn.addEventListener("click", () => {
      const next = current() === "dark" ? "light" : "dark";
      apply(next);
      save(next);
    });
    apply(current());
  }

  // Follow the other tabs if the choice changes there.
  window.addEventListener("storage", (e) => {
    if (e.key === KEY && (e.newValue === "dark" || e.newValue === "light")) apply(e.newValue);
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
