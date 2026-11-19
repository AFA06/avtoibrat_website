(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "avtoibrat.theme"; // shared with the student panel and the legal pages

  // Light/dark toggle: starts from the saved choice, else the system setting.
  var themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var current = root.getAttribute("data-theme") ||
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(KEY, next); } catch (e) { /* private mode: the choice lasts this page only */ }
    });
  }

  // Phone menu: opens under the header, closes on a link click, Esc or a click outside.
  var menuBtn = document.getElementById("menu-toggle");
  var nav = document.getElementById("top-nav");
  function setMenu(open) {
    nav.classList.toggle("is-open", open);
    menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    menuBtn.querySelector("i").className = open ? "ti ti-x" : "ti ti-menu-2";
  }
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () { setMenu(!nav.classList.contains("is-open")); });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) setMenu(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && nav.classList.contains("is-open")) { setMenu(false); menuBtn.focus(); } });
    document.addEventListener("click", function (e) {
      if (nav.classList.contains("is-open") && !e.target.closest("#top-nav, #menu-toggle")) setMenu(false);
    });
  }

  // Header shadow once the page scrolls.
  var top = document.getElementById("top");
  if (top) {
    var onScroll = function () { top.classList.toggle("is-scrolled", window.scrollY > 4); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // «Yozilish» on a category row picks that category in the sign-up form.
  document.querySelectorAll("[data-category]").forEach(function (link) {
    link.addEventListener("click", function () {
      var radio = document.querySelector('input[name="category"][value="' + link.getAttribute("data-category") + '"]');
      if (radio) radio.checked = true;
      var name = document.getElementById("f-name");
      if (name) setTimeout(function () { name.focus({ preventScroll: true }); }, 450);
    });
  });
})();
