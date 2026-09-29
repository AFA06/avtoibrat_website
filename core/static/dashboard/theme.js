/* Entrance + hover motion for the panel, built on Motion (the vanilla Framer Motion build). */
(function () {
  "use strict";

  const M = window.Motion;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Hidden tabs pause animations, which would leave content half-faded, so skip motion there.
  if (!M || reduced || document.visibilityState !== "visible") return;

  const { animate, stagger, inView, hover, press } = M;
  const root = document.documentElement;
  root.classList.add("motion-ready");
  // Safety net: never leave content hidden if animation frames are throttled (background tab).
  setTimeout(() => {
    root.classList.remove("motion-ready");
    document.querySelectorAll("[data-motion], .left-sidebar .nav-item").forEach((el) => {
      el.getAnimations().forEach((a) => a.finish());
      el.style.opacity = "";
      el.style.transform = "";
    });
  }, 2200);

  const SELECTOR = [
    ".page-content-tab .card",
    ".topic-card",
    ".rs-card",
    ".saved-intro",
    ".saved-group",
    ".rs-header",
  ].join(",");

  function tag() {
    document.querySelectorAll(SELECTOR).forEach((el) => el.setAttribute("data-motion", ""));
  }

  function reveal() {
    const items = Array.from(document.querySelectorAll("[data-motion]"));
    // Everything already on screen animates as one staggered wave; the rest reveal on scroll.
    const vh = window.innerHeight;
    const above = items.filter((el) => el.getBoundingClientRect().top < vh);
    const below = items.filter((el) => !above.includes(el));

    animate(above, { opacity: [0, 1], transform: ["translateY(14px) scale(0.985)", "translateY(0) scale(1)"] },
      { duration: 0.5, delay: stagger(0.045, { startDelay: 0.05 }), ease: [0.22, 1, 0.36, 1] });

    below.forEach((el) => {
      inView(el, () => {
        animate(el, { opacity: [0, 1], transform: ["translateY(14px) scale(0.985)", "translateY(0) scale(1)"] },
          { duration: 0.45, ease: [0.22, 1, 0.36, 1] });
      }, { margin: "0px 0px -8% 0px" });
    });
  }

  function sidebar() {
    const links = document.querySelectorAll(".left-sidebar .menu-body .nav-item");
    animate(links, { opacity: [0, 1], transform: ["translateX(-10px)", "translateX(0)"] },
      { duration: 0.4, delay: stagger(0.035), ease: "easeOut" });
  }

  function countUp() {
    document.querySelectorAll(".page-content-tab h3, .page-content-tab .counter").forEach((el) => {
      const text = el.textContent.trim();
      if (!/^\d+$/.test(text) || text.length > 5) return;
      const target = parseInt(text, 10);
      if (target < 2) return;
      animate(0, target, {
        duration: 0.9,
        ease: "easeOut",
        onUpdate: (v) => { el.textContent = Math.round(v); },
      });
    });
  }

  function microInteractions() {
    hover(".btn, .rs-btn, .saved-intro__btn", (el) => {
      animate(el, { transform: "translateY(-1px)" }, { duration: 0.15 });
      return () => animate(el, { transform: "translateY(0)" }, { duration: 0.2 });
    });
    press(".btn, .rs-btn, .topic-card, .rs-card", (el) => {
      animate(el, { scale: 0.98 }, { duration: 0.1 });
      return () => animate(el, { scale: 1 }, { type: "spring", stiffness: 500, damping: 30 });
    });
  }

  function init() {
    tag();
    reveal();
    sidebar();
    countUp();
    microInteractions();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
