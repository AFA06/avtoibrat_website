(function () {
  "use strict";

  const STORAGE_KEY = "avtoibrat.sidebar";
  const COLLAPSED_CLASS = "sidebar-collapsed";
  const DRAWER_QUERY = "(max-width: 991.98px)";
  const THEME_SIDEBAR_CLASSES = ["enlarge-menu", "enlarge-menu-all"];

  const root = document.documentElement;

  function readCollapsed() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === "collapsed";
    } catch (error) {
      return false;
    }
  }

  function saveCollapsed(collapsed) {
    try {
      window.localStorage.setItem(STORAGE_KEY, collapsed ? "collapsed" : "expanded");
    } catch (error) {
      // Storage can be blocked; the sidebar still works, it just won't be remembered.
    }
  }

  // Runs while <head> is parsed so the sidebar never flashes in the wrong state.
  root.classList.toggle(COLLAPSED_CLASS, readCollapsed());

  // A browser can keep serving an older cached copy of the theme script (app.js), which still
  // adds these body classes. Their CSS expands the sidebar on hover, so they are removed whenever added.
  function keepThemeSidebarClassesOff() {
    const body = document.body;
    const strip = () => {
      if (THEME_SIDEBAR_CLASSES.some((name) => body.classList.contains(name))) {
        body.classList.remove(...THEME_SIDEBAR_CLASSES);
      }
    };
    strip();
    new MutationObserver(strip).observe(body, { attributes: true, attributeFilter: ["class"] });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.querySelector(".left-sidebar");
    const toggle = document.getElementById("togglemenu");
    if (!sidebar || !toggle) return;

    keepThemeSidebarClassesOff();

    const drawerMode = window.matchMedia(DRAWER_QUERY);
    const links = sidebar.querySelectorAll(".menu-body .nav-link");
    const tooltip = createTooltip();
    const backdrop = createBackdrop();

    sidebar.id = sidebar.id || "sidebar";
    toggle.setAttribute("aria-controls", sidebar.id);

    function isOpen() {
      return drawerMode.matches ? sidebar.classList.contains("open") : !root.classList.contains(COLLAPSED_CLASS);
    }

    function syncToggle() {
      toggle.setAttribute("aria-expanded", String(isOpen()));
      backdrop.classList.toggle("is-visible", drawerMode.matches && sidebar.classList.contains("open"));
    }

    function setDrawer(open) {
      sidebar.classList.toggle("open", open);
      syncToggle();
    }

    function toggleSidebar() {
      hideTooltip();
      if (drawerMode.matches) {
        setDrawer(!sidebar.classList.contains("open"));
        return;
      }
      const collapsed = !root.classList.contains(COLLAPSED_CLASS);
      root.classList.toggle(COLLAPSED_CLASS, collapsed);
      saveCollapsed(collapsed);
      syncToggle();
    }

    function createBackdrop() {
      const element = document.createElement("div");
      element.className = "sidebar-backdrop";
      document.body.appendChild(element);
      return element;
    }

    function createTooltip() {
      const element = document.createElement("div");
      element.className = "sidebar-tooltip";
      element.setAttribute("role", "tooltip");
      document.body.appendChild(element);
      return element;
    }

    function showTooltip(link) {
      if (drawerMode.matches || !root.classList.contains(COLLAPSED_CLASS)) return;
      const label = link.querySelector("span");
      if (!label) return;

      tooltip.textContent = label.textContent.trim();
      const rect = link.getBoundingClientRect();
      tooltip.style.left = `${rect.right + 12}px`;
      tooltip.style.top = `${rect.top + rect.height / 2}px`;
      tooltip.classList.add("is-visible");
    }

    function hideTooltip() {
      tooltip.classList.remove("is-visible");
    }

    function markCurrentPage() {
      const path = window.location.pathname;
      const homePath = links[0].pathname;
      links.forEach((link) => {
        const target = link.pathname;
        const current = path === target || (target !== homePath && path.startsWith(target));
        link.classList.toggle("active", current);
        if (current) {
          link.setAttribute("aria-current", "page");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    }

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      toggleSidebar();
    });

    backdrop.addEventListener("click", () => setDrawer(false));

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      hideTooltip();
      if (drawerMode.matches && sidebar.classList.contains("open")) {
        setDrawer(false);
        toggle.focus();
      }
    });

    links.forEach((link) => {
      link.addEventListener("mouseenter", () => showTooltip(link));
      link.addEventListener("focus", () => showTooltip(link));
      link.addEventListener("mouseleave", hideTooltip);
      link.addEventListener("blur", hideTooltip);
      link.addEventListener("click", hideTooltip);
    });

    sidebar.addEventListener("scroll", hideTooltip, true);
    window.addEventListener("resize", hideTooltip);

    drawerMode.addEventListener("change", () => {
      setDrawer(false);
      hideTooltip();
    });

    markCurrentPage();
    syncToggle();
  });
})();
