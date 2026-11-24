(function () {
  "use strict";
  if (window.avtoNotesCleanup) window.avtoNotesCleanup();
  const library = document.getElementById("notes-library");
  const reader = document.getElementById("notes-reader");
  const root = library || reader;
  if (!root) return;
  const copy = JSON.parse(document.getElementById("notes-copy").textContent);
  const controller = new AbortController();
  const on = (el, type, fn, options = {}) => el.addEventListener(type, fn, { ...options, signal: controller.signal });
  let searchTimer;
  window.avtoNotesCleanup = () => {
    controller.abort();
    clearTimeout(searchTimer);
    document.body.classList.remove("notes-focus-open");
    reader?.querySelector("dialog[open]")?.close();
    reader?.querySelectorAll("video").forEach(video => { if (!video.paused) video.pause(); });
    window.avtoNotesCleanup = null;
  };
  on(document, "pjax:load", () => { if (!root.isConnected && window.avtoNotesCleanup) window.avtoNotesCleanup(); });
  const key = slug => `avtoibrat.notes.v1:${root.dataset.scope}:${slug}`;
  function read(slug, count, first = 1) {
    let value;
    try { value = JSON.parse(localStorage.getItem(key(slug)) || "{}"); } catch (_) { /* Storage may be unavailable. */ }
    value = value && typeof value === "object" ? value : {};
    const valid = n => Number.isInteger(n) && n > 0 && n <= count;
    return {
      page: valid(value.page) ? value.page : first,
      seen: Array.isArray(value.seen) ? [...new Set(value.seen.filter(valid))] : [],
      saved: Array.isArray(value.saved) ? [...new Set(value.saved.filter(valid))] : [],
      updated: Number.isFinite(value.updated) ? value.updated : 0,
    };
  }
  function write(slug, value) { try { localStorage.setItem(key(slug), JSON.stringify(value)); } catch (_) { /* Reading still works without storage. */ } }
  const translit = { а:"a",б:"b",в:"v",г:"g",д:"d",е:"e",ё:"yo",ж:"j",з:"z",и:"i",й:"y",к:"k",л:"l",м:"m",н:"n",о:"o",п:"p",р:"r",с:"s",т:"t",у:"u",ф:"f",х:"x",ц:"ts",ч:"ch",ш:"sh",щ:"sh",ъ:"",ы:"i",ь:"",э:"e",ю:"yu",я:"ya",ў:"o",қ:"q",ғ:"g",ҳ:"h" };
  const fold = value => value.toLowerCase().normalize("NFKC").replace(/[а-яёўқғҳ]/g, c => translit[c] ?? c).replace(/[‘’ʻʼ'`ʹ]/g, "").replace(/\s+/g, " ").trim();
  const matches = (value, words) => words.every(word => value.includes(word));
  const node = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
  const fallbackTitle = slide => slide.title || `${copy.page} ${slide.number}`;

  if (library) {
    const catalog = JSON.parse(document.getElementById("notes-catalog").textContent);
    let recent = null;
    catalog.forEach(topic => {
      const state = read(topic.slug, topic.slides.length, topic.start_page);
      if (state.seen.length) library.querySelector(`[data-progress="${topic.slug}"]`).textContent = `${state.seen.length} / ${topic.slides.length} · ${copy.viewed.toLowerCase()}`;
      if (state.updated && (!recent || state.updated > recent.state.updated)) recent = { topic, state };
      topic.slides.forEach(slide => { slide.search = fold(`${topic.title} ${slide.title} ${slide.text}`); });
    });
    if (recent) {
      const link = document.getElementById("notes-resume");
      link.href = `${recent.topic.url}?slide=${recent.state.page}`;
      document.getElementById("notes-resume-title").textContent = recent.topic.title;
      document.getElementById("notes-resume-page").textContent = `${copy.page} ${recent.state.page} / ${recent.topic.slides.length}`;
      link.hidden = false;
    }
    const input = document.getElementById("notes-search"), clear = document.getElementById("notes-clear");
    const results = document.getElementById("notes-results"), list = document.getElementById("notes-result-list"), empty = document.getElementById("notes-empty");
    function search() {
      const words = fold(input.value).split(" ").filter(Boolean);
      document.getElementById("notes-topics").hidden = !!words.length;
      clear.hidden = !input.value;
      results.hidden = !words.length;
      empty.hidden = true;
      list.replaceChildren();
      if (!words.length) return;
      const fragment = document.createDocumentFragment();
      let count = 0;
      catalog.forEach(topic => topic.slides.forEach(slide => {
        if (!matches(slide.search, words)) return;
        count++;
        const link = node("a", "notes-result");
        link.href = `${topic.url}?slide=${slide.number}`;
        const img = node("img"); img.src = slide.thumbnail; img.alt = ""; img.loading = "lazy"; img.width = 120; img.height = 68;
        const body = node("span");
        body.append(node("small", "", `${topic.title} · ${copy.page} ${slide.number}`), node("strong", "", fallbackTitle(slide)), node("p", "", slide.text));
        link.append(img, body); fragment.append(link);
      }));
      list.append(fragment);
      document.getElementById("notes-result-count").textContent = `${copy.matches}: ${count}`;
      empty.hidden = !!count;
    }
    on(input, "input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(search, 140); });
    on(clear, "click", () => { input.value = ""; search(); input.focus(); });
    return;
  }

  const deck = JSON.parse(document.getElementById("notes-deck").textContent);
  const state = read(deck.slug, deck.slides.length, deck.start_page);
  const slides = deck.slides;
  const byId = id => document.getElementById(id);
  const links = [...byId("reader-list").querySelectorAll("[data-slide]")];
  const image = byId("reader-image"), save = byId("reader-save"), input = byId("reader-page"), dialog = byId("reader-zoom");
  let page = Number(root.dataset.page), filter = "all", zoom = 1, focused = false;
  const url = new URL(location.href);
  const hashPage = /^#slide-(\d+)$/.exec(location.hash);
  if (hashPage && Number(hashPage[1]) > 0 && Number(hashPage[1]) <= slides.length) page = Number(hashPage[1]);
  else if (!url.searchParams.has("slide")) page = state.page;
  slides.forEach(slide => { slide.search = fold(`${slide.title} ${slide.paragraphs.join(" ")}`); });

  function updateList() {
    const words = fold(byId("reader-search").value).split(" ").filter(Boolean);
    let count = 0;
    links.forEach((link, i) => {
      const slide = slides[i];
      link.hidden = !matches(slide.search, words) || (filter === "saved" ? !state.saved.includes(slide.number) : filter !== "all" && filter !== slide.kind);
      if (!link.hidden) count++;
      const active = slide.number === page;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
      link.querySelector(".notes-index__star").hidden = !state.saved.includes(slide.number);
    });
    const visible = links.filter(link => !link.hidden).map(link => Number(link.dataset.slide));
    [["reader-prev", visible.slice().reverse().find(n => n < page)], ["reader-next", visible.find(n => n > page)]].forEach(([id, target]) => {
      const button = byId(id), disabled = target === undefined;
      button.setAttribute("aria-disabled", String(disabled)); button.tabIndex = disabled ? -1 : 0;
      if (!disabled) button.href = `?slide=${target}`;
    });
    byId("reader-count").textContent = `${count} ${copy.slides}`;
    byId("reader-empty").hidden = !!count;
    byId("reader-empty").textContent = filter === "saved" && !state.saved.length ? copy.saved_empty : copy.empty;
  }
  function setZoom(value) {
    zoom = Math.max(1, Math.min(4, value));
    byId("zoom-image").style.width = `${zoom * 100}%`;
    byId("zoom-image").classList.toggle("is-zoomed", zoom > 1);
    byId("zoom-reset").textContent = `${Math.round(zoom * 100)}%`;
    byId("zoom-out").disabled = zoom === 1;
    byId("zoom-in").disabled = zoom === 4;
  }
  function setFocus(value) {
    focused = value;
    root.classList.toggle("is-focus", value);
    document.body.classList.toggle("notes-focus-open", value);
    byId("reader-focus").setAttribute("aria-pressed", String(value));
    byId("reader-focus").title = byId("reader-focus").ariaLabel = value ? copy.exit_focus : copy.focus;
    if (value) {
      byId("reader-stage").setAttribute("role", "dialog");
      byId("reader-stage").setAttribute("aria-modal", "true");
      byId("reader-focus").focus();
    } else {
      byId("reader-stage").removeAttribute("role");
      byId("reader-stage").removeAttribute("aria-modal");
    }
  }
  function show(number, changeUrl = true) {
    number = Number(number);
    if (!Number.isInteger(number) || number < 1 || number > slides.length) { input.value = page; return; }
    page = number;
    const slide = slides[page - 1];
    const title = fallbackTitle(slide);
    byId("reader-title").textContent = title;
    byId("reader-position").textContent = `${page} / ${slides.length}`;
    byId("reader-kind").textContent = slide.kind === "example" ? copy.example : copy.rule;
    byId("reader-kind").classList.toggle("is-example", slide.kind === "example");
    byId("reader-image-error").hidden = true;
    image.src = slide.image; image.alt = title;
    const video = byId("reader-video");
    if (video.getAttribute("src") !== (slide.video || null)) {
      if (video.getAttribute("src")) video.pause();
      if (slide.video) video.src = slide.video; else video.removeAttribute("src");
    }
    byId("reader-video-section").hidden = !slide.video;
    byId("zoom-image").src = slide.image; byId("zoom-image").alt = title;
    byId("zoom-title").textContent = `${copy.page} ${page} · ${deck.title}`;
    input.value = page;
    const saved = state.saved.includes(page);
    save.setAttribute("aria-pressed", String(saved));
    save.title = save.ariaLabel = saved ? copy.unsave : copy.save;
    save.firstElementChild.className = saved ? "ti ti-star-filled" : "ti ti-star";
    const paragraphs = slide.paragraphs.length ? slide.paragraphs : [copy.no_text];
    byId("reader-paragraphs").replaceChildren(...paragraphs.map(p => node("p", "", p)));
    byId("reader-example-note").hidden = slide.kind !== "example";
    byId("reader-end").hidden = page !== slides.length;
    [["reader-prev", page - 1], ["reader-next", page + 1]].forEach(([id, target]) => {
      const el = byId(id), disabled = target < 1 || target > slides.length;
      el.setAttribute("aria-disabled", String(disabled)); el.tabIndex = disabled ? -1 : 0;
      el.href = `?slide=${Math.max(1, Math.min(target, slides.length))}`;
    });
    state.page = page; state.updated = Date.now();
    if (!state.seen.includes(page)) state.seen.push(page);
    write(deck.slug, state); updateList();
    if (changeUrl) {
      const target = new URL(location.href); target.searchParams.set("slide", page); target.hash = "";
      history.replaceState(history.state, "", target.pathname + target.search);
    }
    // The language switch keeps a student's place on the matching deck.
    document.querySelectorAll('.topbar input[name="next"]').forEach(el => { el.value = location.pathname + location.search; });
    setZoom(1);
    byId("zoom-canvas").scrollTo(0, 0);
    // Fetch just the next page in advance, rather than the whole presentation.
    if (slides[page]) { const nextImage = new Image(); nextImage.src = slides[page].image; }
  }
  function move(step) {
    // Previous/next follows the selected rules/examples/bookmarks filter.
    const visible = links.filter(link => !link.hidden).map(link => Number(link.dataset.slide));
    const next = step > 0 ? visible.find(n => n > page) : visible.slice().reverse().find(n => n < page);
    if (next !== undefined) show(next);
  }
  on(byId("reader-list"), "click", event => {
    const link = event.target.closest("[data-slide]");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault(); show(link.dataset.slide);
    if (matchMedia("(max-width: 767px)").matches) {
      byId("reader-stage").style.scrollMarginTop = "80px";
      byId("reader-stage").scrollIntoView({ behavior: "instant", block: "start" });
    }
  });
  on(byId("reader-search"), "input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(updateList, 100); });
  root.querySelectorAll("[data-filter]").forEach(button => on(button, "click", () => {
    filter = button.dataset.filter;
    root.querySelectorAll("[data-filter]").forEach(b => { const active = b === button; b.classList.toggle("is-active", active); b.setAttribute("aria-pressed", String(active)); });
    updateList();
  }));
  on(save, "click", () => {
    if (state.saved.includes(page)) state.saved = state.saved.filter(n => n !== page); else state.saved.push(page);
    show(page, false);
  });
  on(byId("reader-prev"), "click", e => { e.preventDefault(); move(-1); });
  on(byId("reader-next"), "click", e => { e.preventDefault(); move(1); });
  on(input, "change", () => show(input.value));
  on(input, "keydown", e => { if (e.key === "Enter") { show(input.value); input.blur(); } });
  on(byId("reader-focus"), "click", () => setFocus(!focused));
  on(byId("reader-enlarge"), "click", () => { dialog.showModal(); setZoom(1); });
  on(byId("zoom-close"), "click", () => dialog.close());
  on(byId("zoom-in"), "click", () => setZoom(zoom + .5));
  on(byId("zoom-out"), "click", () => setZoom(zoom - .5));
  on(byId("zoom-reset"), "click", () => setZoom(1));
  on(dialog, "click", e => { if (e.target === dialog) dialog.close(); });
  on(image, "error", () => { byId("reader-image-error").hidden = false; byId("reader-text").open = true; });
  on(image, "load", () => { byId("reader-image-error").hidden = true; });
  on(byId("reader-retry"), "click", () => { byId("reader-image-error").hidden = true; const retry = new URL(slides[page - 1].image, location.href); retry.searchParams.set("retry", Date.now()); image.src = retry.href; });
  on(document, "keydown", e => {
    if (!root.isConnected || e.altKey || e.ctrlKey || e.metaKey || (e.shiftKey && e.key !== "Tab")) return;
    if (e.key === "Escape" && focused && !dialog.open) { setFocus(false); byId("reader-focus").focus(); return; }
    if (focused && !dialog.open && e.key === "Tab") {
      const controls = [...byId("reader-stage").querySelectorAll('a[href],button,input,summary')].filter(el => !el.disabled && el.tabIndex !== -1 && el.getClientRects().length && !el.closest("[hidden]"));
      if (controls.length && e.shiftKey && e.target === controls[0]) { e.preventDefault(); controls[controls.length - 1].focus(); }
      else if (controls.length && !e.shiftKey && e.target === controls[controls.length - 1]) { e.preventDefault(); controls[0].focus(); }
    }
    if (e.target.closest("input,textarea,select,[contenteditable=true]") || dialog.open) return;
    if (e.key === "ArrowRight") { e.preventDefault(); move(1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); move(-1); }
  });
  on(window, "popstate", () => { if (root.isConnected) { const value = Number(new URL(location.href).searchParams.get("slide") || 1); show(value, false); } });
  const toggle = node("button", "notes-index-toggle");
  toggle.innerHTML = '<i class="ti ti-chevron-down" aria-hidden="true"></i>';
  toggle.setAttribute("aria-label", copy.contents); toggle.title = copy.contents;
  toggle.type = "button"; toggle.setAttribute("aria-expanded", "false"); toggle.setAttribute("aria-controls", "reader-list");
  byId("reader-list").closest("aside").querySelector(".notes-index__head").append(toggle);
  on(toggle, "click", () => { const open = toggle.closest("aside").classList.toggle("is-open"); toggle.setAttribute("aria-expanded", String(open)); });
  byId("reader-text").open = matchMedia("(max-width: 767px)").matches;
  show(page);
  const active = links[page - 1];
  if (active) byId("reader-list").scrollTop = Math.max(0, active.offsetTop - byId("reader-list").offsetTop - 20);
})();
