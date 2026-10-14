(function () {
  "use strict";

  // Student → Mavzulashtirilgan testlar: search and section filter, and the start sheet of a topic.
  const config = window.TOPIC_TESTS || { quickSize: 20, minutesPerQuestion: 1 };
  const sheet = document.getElementById("tp-sheet");
  const search = document.getElementById("tp-search");
  const noResults = document.getElementById("tp-no-results");
  const groups = Array.from(document.querySelectorAll(".tp-group"));
  const cards = Array.from(document.querySelectorAll(".tp-card"));
  const chips = Array.from(document.querySelectorAll(".tp-chip"));

  // ---------- Filtering ----------
  // Apostrophes come in many shapes in Uzbek text (o‘, o', oʻ); compare without them.
  const normalize = (text) => text.toLowerCase().replace(/[‘’ʻʼ'`]/g, "").replace(/\s+/g, " ").trim();
  cards.forEach((card) => (card.dataset.search = normalize(card.dataset.name)));

  let activeGroup = "";

  function applyFilter() {
    const query = search ? normalize(search.value) : "";
    let shown = 0;
    groups.forEach((group) => {
      const groupMatches = !activeGroup || group.dataset.group === activeGroup;
      let visible = 0;
      group.querySelectorAll(".tp-card").forEach((card) => {
        const match = groupMatches && (!query || card.dataset.search.includes(query));
        card.hidden = !match;
        visible += match;
      });
      group.hidden = visible === 0;
      shown += visible;
    });
    if (noResults) noResults.hidden = shown > 0;
  }

  if (search) {
    search.addEventListener("input", applyFilter);
    search.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && search.value) {
        search.value = "";
        applyFilter();
      }
    });
    // "/" jumps to the search box, like on most sites with search.
    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && document.activeElement === document.body) {
        event.preventDefault();
        search.focus();
      }
    });
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      activeGroup = chip.dataset.filter;
      chips.forEach((c) => {
        const on = c === chip;
        c.classList.toggle("is-active", on);
        c.setAttribute("aria-selected", on ? "true" : "false");
      });
      chip.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
      applyFilter();
    });
  });

  // ---------- Start sheet ----------
  if (!sheet) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const modes = Object.fromEntries(
    Array.from(sheet.querySelectorAll(".tp-mode")).map((link) => [link.dataset.mode, link])
  );

  function setMode(link, url, count) {
    link.hidden = count === 0 && link.dataset.mode !== "mistakes";
    link.classList.toggle("is-disabled", count === 0);
    link.classList.remove("is-loading");
    if (count) {
      link.href = url;
      link.removeAttribute("aria-disabled");
    } else {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
    }
    link.querySelectorAll("[data-count]").forEach((el) => (el.textContent = count));
    link.querySelectorAll("[data-minutes]").forEach((el) => (el.textContent = count * config.minutesPerQuestion));
  }

  function openSheet(card) {
    const total = Number(card.dataset.total);
    const mistakes = Number(card.dataset.mistakes);
    const url = card.dataset.url + "?mode=";

    sheet.querySelector("#tp-sheet-title").textContent = card.dataset.name;
    sheet.querySelector('[data-stat="total"]').textContent = total;
    sheet.querySelector('[data-stat="learned"]').textContent = card.dataset.learned;
    sheet.querySelector('[data-stat="mistakes"]').textContent = mistakes;

    // A topic with no more questions than a quick test only offers «all questions».
    setMode(modes.quick, url + "quick", total > config.quickSize ? config.quickSize : 0);
    setMode(modes.all, url + "all", total);
    setMode(modes.mistakes, url + "mistakes", mistakes);
    sheet.querySelector("[data-hint-some]").hidden = mistakes === 0;
    sheet.querySelector("[data-hint-none]").hidden = mistakes > 0;

    sheet.showModal();
    requestAnimationFrame(() => sheet.classList.add("is-open"));
  }

  function closeSheet() {
    if (!sheet.open) return;
    sheet.classList.remove("is-open");
    if (reduceMotion) {
      sheet.close();
      return;
    }
    const panel = sheet.querySelector(".tp-sheet__panel");
    const done = () => {
      panel.removeEventListener("transitionend", done);
      if (!sheet.classList.contains("is-open")) sheet.close();
    };
    panel.addEventListener("transitionend", done);
    setTimeout(done, 350); // in case the transition never fires
  }

  cards.forEach((card) => card.addEventListener("click", () => openSheet(card)));
  sheet.querySelector("[data-close]").addEventListener("click", closeSheet);
  sheet.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeSheet();
  });
  // A click on the dimmed backdrop (the dialog itself, outside the panel) closes the sheet.
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) closeSheet();
  });

  Object.values(modes).forEach((link) => {
    link.addEventListener("click", (event) => {
      if (!link.getAttribute("href") || link.classList.contains("is-loading")) {
        event.preventDefault();
        return;
      }
      link.classList.add("is-loading");
    });
  });

  // Coming back with the browser's Back button restores the page from cache with the sheet still open.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted && sheet.open) {
      sheet.classList.remove("is-open");
      sheet.close();
    }
  });
})();
