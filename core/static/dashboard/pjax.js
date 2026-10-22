/* Panel navigation without reloading the page.
   A click in the sidebar fetches the next page in the background and swaps only the content area:
   the sidebar, top bar, theme and scripts stay exactly as they are, so nothing flashes or jumps.
   Anything unexpected falls back to a normal page load. */
(function () {
  "use strict";

  const content = () => document.querySelector(".page-content-tab");
  if (!content() || !document.querySelector(".left-sidebar") || !window.fetch || !window.DOMParser) return;

  const COMMON_ASSETS = ["bootstrap.min.css", "icons.min.css", "app.min.css", "user-menu.css", "sidebar.css", "theme.css"];
  const COMMON_SCRIPTS = ["sidebar.js", "protect.js", "app.js", "theme-toggle.js", "motion.js", "theme.js", "jquery", "bootstrap"];
  const CACHE_MS = 30000;
  const cache = new Map(); // url -> { at, promise }
  let current = location.pathname + location.search;
  let busy = false;

  const isCommon = (value, list) => list.some((name) => value.includes(name));
  const sameDoc = (url) => url.origin === location.origin;

  function eligible(link, event) {
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    if (link.target && link.target !== "_self") return false;
    if (link.hasAttribute("download") || link.dataset.noPjax !== undefined) return false;
    const url = new URL(link.href, location.href);
    if (!sameDoc(url) || /\/logout\/?$/.test(url.pathname) || /\/(admin|media|static)\//.test(url.pathname)) return false;
    return true;
  }

  function fetchPage(url) {
    const hit = cache.get(url);
    if (hit && Date.now() - hit.at < CACHE_MS) return hit.promise;
    const promise = fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "pjax" } }).then((response) => {
      const type = response.headers.get("content-type") || "";
      if (!response.ok || !type.includes("text/html") || !sameDoc(new URL(response.url))) throw new Error("not a panel page");
      return response.text().then((html) => ({ html, url: response.url }));
    });
    cache.set(url, { at: Date.now(), promise });
    promise.catch(() => cache.delete(url));
    return promise;
  }

  // ---- Head: page-specific styles are swapped, the common ones stay ----
  const pageStyles = () => Array.from(document.head.querySelectorAll('link[rel="stylesheet"], style')).filter((node) => node.tagName === "STYLE" || !isCommon(node.getAttribute("href") || "", COMMON_ASSETS));

  async function swapStyles(doc) {
    const wanted = Array.from(doc.head.querySelectorAll('link[rel="stylesheet"], style')).filter((node) => node.tagName === "STYLE" || !isCommon(node.getAttribute("href") || "", COMMON_ASSETS));
    const old = pageStyles();
    const keep = new Set();
    const loading = [];
    wanted.forEach((node) => {
      const same = old.find((o) => o.tagName === node.tagName && (node.tagName === "STYLE" ? o.textContent === node.textContent : o.getAttribute("href") === node.getAttribute("href")));
      if (same) { keep.add(same); return; }
      const copy = node.cloneNode(true);
      if (copy.tagName === "LINK") loading.push(new Promise((resolve) => { copy.onload = copy.onerror = resolve; setTimeout(resolve, 1500); }));
      document.head.appendChild(copy);
    });
    await Promise.all(loading);
    old.forEach((node) => !keep.has(node) && node.remove());
  }

  // ---- Scripts of the new page ----
  function pageScripts(doc, container) {
    const list = Array.from(container.querySelectorAll("script")).filter((script) => !script.closest(".footer") && !/document\.write/.test(script.textContent));
    doc.body.querySelectorAll("script").forEach((script) => {
      if (container.contains(script) || script.closest(".footer")) return;
      const src = script.getAttribute("src") || "";
      if (src ? isCommon(src, COMMON_SCRIPTS) : /document\.write|avtoibrat\.theme/.test(script.textContent)) return;
      list.push(script);
    });
    return list;
  }

  // Handlers waiting for DOMContentLoaded/load would never fire on a page that is already loaded.
  async function runScripts(scripts) {
    const originalAdd = document.addEventListener;
    document.addEventListener = function (type, handler, options) {
      if (type === "DOMContentLoaded") { setTimeout(handler, 0); return; }
      return originalAdd.call(this, type, handler, options);
    };
    try {
      for (const script of scripts) {
        const src = script.getAttribute("src");
        if (src) {
          await new Promise((resolve) => {
            const copy = document.createElement("script");
            copy.src = src;
            copy.onload = copy.onerror = resolve;
            document.body.appendChild(copy);
          });
        } else {
          try { (0, eval)(script.textContent); } catch (error) { console.error("pjax inline script:", error); }
        }
      }
    } finally {
      document.addEventListener = originalAdd;
    }
  }

  function markCurrent() {
    const links = document.querySelectorAll(".left-sidebar .menu-body .nav-link");
    const path = location.pathname;
    const home = links[0] ? links[0].pathname : "";
    links.forEach((link) => {
      const on = path === link.pathname || (link.pathname !== home && path.startsWith(link.pathname));
      link.classList.toggle("active", on);
      if (on) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
  }

  async function go(rawUrl, push) {
    const target = new URL(rawUrl, location.href);
    const key = target.pathname + target.search;
    if (busy) return;
    if (key === current && push) return;
    busy = true;
    const area = content();
    area.classList.add("pjax-out");
    try {
      const [{ html, url }] = await Promise.all([fetchPage(target.href), new Promise((r) => setTimeout(r, 90))]);
      const doc = new DOMParser().parseFromString(html, "text/html");
      const fresh = doc.querySelector(".page-content-tab");
      if (!fresh || !doc.querySelector(".left-sidebar")) throw new Error("not a panel page");

      await swapStyles(doc);
      document.title = doc.title;
      const finalUrl = new URL(url);
      if (push) history.pushState({ pjax: true }, "", finalUrl.pathname + finalUrl.search);
      current = location.pathname + location.search;

      // Everything but the footer (it stays, with its year) is replaced.
      const footer = area.querySelector(":scope > .footer");
      Array.from(area.childNodes).forEach((node) => node !== footer && node.remove());
      Array.from(fresh.childNodes).forEach((node) => {
        if (node.nodeType === 1 && node.classList.contains("footer")) return;
        area.insertBefore(document.importNode(node, true), footer);
      });
      // Language switchers return to the page being shown.
      document.querySelectorAll('.topbar input[name="next"]').forEach((input) => { input.value = location.pathname; });
      markCurrent();
      window.scrollTo(0, 0);

      if (window.panelMotion) window.panelMotion.run();
      await runScripts(pageScripts(doc, fresh));
      document.dispatchEvent(new CustomEvent("pjax:load"));
      document.querySelector(".left-sidebar")?.classList.remove("open");
      document.querySelector(".sidebar-backdrop")?.classList.remove("is-visible");
    } catch (error) {
      console.warn("pjax fallback:", error);
      location.href = target.href; // fall back to a normal page load
      return;
    } finally {
      area.classList.remove("pjax-out");
      busy = false;
    }
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest(".left-sidebar .menu-body a.nav-link");
    if (!eligible(link, event)) return;
    event.preventDefault();
    go(link.href, true);
  });

  // Prepare the page while the pointer rests on a link.
  const warm = (event) => {
    const link = event.target.closest && event.target.closest(".left-sidebar .menu-body a.nav-link");
    if (link && eligible(link, { button: 0 })) fetchPage(new URL(link.href, location.href).href).catch(() => {});
  };
  document.addEventListener("mouseover", warm, { passive: true });
  document.addEventListener("touchstart", warm, { passive: true });

  history.replaceState({ pjax: true }, "");
  window.addEventListener("popstate", () => {
    if (location.pathname + location.search !== current) go(location.href, false);
  });
})();
