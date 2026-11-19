(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "avtoibrat.theme"; // shared with the student panel and the legal pages

  // Light/dark toggle: starts from the saved choice, else the system setting.
  var themeBtn = document.getElementById("st-theme");
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
  var menuBtn = document.getElementById("st-menu");
  var nav = document.getElementById("st-nav");
  function setMenu(open) {
    if (!nav || !menuBtn) return;
    nav.classList.toggle("is-open", open);
    menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    menuBtn.querySelector("i").className = open ? "ti ti-x" : "ti ti-menu-2";
  }
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () { setMenu(!nav.classList.contains("is-open")); });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) setMenu(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setMenu(false); });
    document.addEventListener("click", function (e) {
      if (nav.classList.contains("is-open") && !e.target.closest("#st-nav, #st-menu")) setMenu(false);
    });
  }

  // Header gets a border once the page scrolls.
  var top = document.getElementById("st-top");
  if (top) {
    var onScroll = function () { top.classList.toggle("is-scrolled", window.scrollY > 8); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // «Yozilish» on a course card picks that category in the sign-up form.
  var select = document.getElementById("f-category");
  document.querySelectorAll("[data-category]").forEach(function (link) {
    link.addEventListener("click", function () {
      if (select) select.value = link.getAttribute("data-category");
      var name = document.getElementById("f-name");
      if (name) setTimeout(function () { name.focus({ preventScroll: true }); }, 400);
    });
  });

  // Sections fade in as they scroll into view.
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    root.classList.add("st-js");
    var items = document.querySelectorAll(".st-head, .st-steps li, .st-course, .st-person, .st-review, .st-faq__list, .st-apply > *");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add("is-in"); io.unobserve(entry.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    items.forEach(function (el, i) {
      el.classList.add("st-reveal");
      el.style.transitionDelay = (i % 4) * 70 + "ms";
      io.observe(el);
    });
  }
})();
