/* Shpargalka: search, section chips with scroll-spy, and starred cards kept on this device. */
(function () {
  "use strict";

  const root = document.getElementById("cs");
  if (!root) return;

  const STORAGE_KEY = "avtoibrat.cheatsheet.pins";
  const $ = (selector, scope = root) => scope.querySelector(selector);
  const $$ = (selector, scope = root) => Array.from(scope.querySelectorAll(selector));

  const search = $("#cs-search");
  const nav = $("#cs-nav");
  const chips = $$(".cs-chip", nav);
  const sections = $$("[data-section]");
  const items = $$("[data-item]");
  const emptyNote = $("#cs-empty");
  const pinsBox = $("#cs-pins");
  const pinsList = $("#cs-pins-list");
  const pinCount = $("#cs-pin-count");
  const toTop = $("#cs-top");

  // ---------- Sticky offset: the panel's top bar may be fixed, so chips sit right below it ----------
  const topbar = document.querySelector(".topbar");
  if (topbar && /fixed|sticky/.test(getComputedStyle(topbar).position)) {
    root.style.setProperty("--cs-sticky", `${topbar.offsetHeight}px`);
  }

  // ---------- Starred cards ----------
  const readPins = () => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; } catch (e) { return []; }
  };
  const writePins = (ids) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(ids)); } catch (e) { /* storage unavailable: pins last for this visit only */ }
  };
  let pins = readPins().filter((id) => items.some((item) => item.dataset.id === id));

  function renderPins() {
    items.forEach((item) => {
      const on = pins.includes(item.dataset.id);
      item.querySelector("[data-pin]").setAttribute("aria-pressed", String(on));
      item.querySelector("[data-pin] i").className = on ? "fas fa-star" : "far fa-star";
    });

    pinsList.textContent = "";
    // One box per topic, in the page's topic order, each card on its own row.
    sections.forEach((section) => {
      const starred = items.filter((item) => pins.includes(item.dataset.id) && section.contains(item));
      if (!starred.length) return;
      const group = document.createElement("div");
      group.className = "cs-pin-group " + [...section.classList].filter((c) => /^cs-s\d/.test(c)).join(" ");
      const head = document.createElement("h3");
      head.className = "cs-pin-group__head";
      head.append(section.querySelector(".cs-section__icon").cloneNode(true), section.querySelector(".cs-section__head h2").textContent);
      const count = document.createElement("b");
      count.textContent = String(starred.length);
      head.appendChild(count);
      group.appendChild(head);
      starred.forEach((original) => {
        const copy = original.cloneNode(true);
        copy.removeAttribute("data-item");
        copy.classList.remove("cs-reveal", "is-in", "is-filtered");
        group.appendChild(copy);
      });
      pinsList.appendChild(group);
    });
    pinsBox.classList.toggle("has-items", pins.length > 0);
    pinCount.textContent = String(pins.length);
  }

  function togglePin(id, button) {
    pins = pins.includes(id) ? pins.filter((x) => x !== id) : pins.concat(id);
    writePins(pins);
    renderPins();
    if (button.isConnected) {
      button.classList.remove("is-pop");
      void button.offsetWidth;
      button.classList.add("is-pop");
    }
  }

  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-pin]");
    if (!button) return;
    const card = button.closest("[data-id]");
    if (card) togglePin(card.dataset.id, button);
  });

  // ---------- Search ----------
  const normalize = (text) => text.toLowerCase().replace(/[ʻʼ'‘’`]/g, "").replace(/\s+/g, " ").trim();
  items.forEach((item) => { item.dataset.text = normalize(item.textContent); });

  function applyFilter() {
    const query = normalize(search.value);
    let shown = 0;
    items.forEach((item) => {
      const match = !query || item.dataset.text.includes(query);
      item.classList.toggle("is-filtered", !match);
      if (match) shown += 1;
    });
    $$("[data-group]").forEach((group) => {
      group.classList.toggle("is-filtered", !group.querySelector("[data-item]:not(.is-filtered)"));
    });
    sections.forEach((section) => {
      section.classList.toggle("is-filtered", !section.querySelector("[data-item]:not(.is-filtered)"));
    });
    emptyNote.hidden = shown > 0;
  }
  search.addEventListener("input", () => { showPinsView(false); applyFilter(); });
  search.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { search.value = ""; applyFilter(); search.blur(); }
  });

  // "/" jumps to the search box. The handler lives on document, so it is registered once and finds the live input.
  if (!window.__csSlashKey) {
    window.__csSlashKey = true;
    document.addEventListener("keydown", (event) => {
      const box = document.getElementById("cs-search");
      if (!box || event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      if (/^(input|textarea|select)$/i.test(document.activeElement.tagName)) return;
      event.preventDefault();
      box.focus();
    });
  }

  // ---------- Chips: jump to a section, and follow the scroll ----------
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const target = document.getElementById(chip.dataset.target);
      if (!target) return;
      const pinsView = chip.dataset.target === "cs-pins";
      showPinsView(pinsView);
      if (pinsView) { setActive("cs-pins"); window.scrollTo({ top: 0, behavior: prefersReduced ? "auto" : "smooth" }); return; }
      target.scrollIntoView({ behavior: prefersReduced ? "auto" : "smooth", block: "start" });
    });
  });

  // Starred cards live on their own view: opened from the "Belgilanganlar" chip, never above the sections.
  const main = pinsBox.parentElement;
  function showPinsView(on) {
    main.classList.toggle("is-pins-view", on);
    pinsBox.classList.toggle("is-open", on);
  }

  function setActive(id) {
    chips.forEach((chip) => {
      const on = chip.dataset.target === id;
      chip.classList.toggle("is-active", on);
      if (on) {
        const left = chip.offsetLeft - (nav.clientWidth - chip.offsetWidth) / 2;
        nav.scrollTo({ left, behavior: prefersReduced ? "auto" : "smooth" });
      }
    });
  }

  if ("IntersectionObserver" in window) {
    const visible = new Map();
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((entry) => visible.set(entry.target.id, entry.isIntersecting ? entry.intersectionRatio : 0));
      let best = null;
      sections.forEach((section) => {
        if ((visible.get(section.id) || 0) > 0 && (best === null || sections.indexOf(section) < sections.indexOf(best))) best = section;
      });
      if (best && !main.classList.contains("is-pins-view")) setActive(best.id);
    }, { rootMargin: "-120px 0px -55% 0px", threshold: [0, 0.01] });
    sections.forEach((section) => spy.observe(section));

    const reveal = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        reveal.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -6% 0px" });
    items.forEach((item, index) => {
      item.classList.add("cs-reveal");
      item.style.transitionDelay = `${Math.min(index % 6, 5) * 40}ms`;
      reveal.observe(item);
    });

    const stuck = new IntersectionObserver(([entry]) => nav.classList.toggle("is-stuck", !entry.isIntersecting), { rootMargin: "0px" });
    const sentinel = document.createElement("div");
    sentinel.style.cssText = "height:1px;margin-top:-1px;pointer-events:none";
    nav.before(sentinel);
    stuck.observe(sentinel);
  }

  // ---------- Back to top ----------
  const onScroll = () => { toTop.hidden = window.scrollY < 700; };
  window.addEventListener("scroll", onScroll, { passive: true });
  toTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: prefersReduced ? "auto" : "smooth" }));

  renderPins();
  onScroll();
})();
