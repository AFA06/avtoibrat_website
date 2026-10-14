(function () {
  "use strict";

  // Contents list built from the document's section headings, with the current section highlighted.
  const content = document.getElementById("lg-content");
  const toc = document.getElementById("lg-toc");
  const headings = content ? Array.from(content.querySelectorAll("h2[id]")) : [];

  if (toc && headings.length) {
    const links = headings.map((heading) => {
      const link = document.createElement("a");
      link.href = `#${heading.id}`;
      const number = heading.querySelector(".lg-num");
      const title = Array.from(heading.childNodes)
        .filter((node) => node !== number)
        .map((node) => node.textContent)
        .join("")
        .trim();
      link.textContent = number ? `${number.textContent}. ${title}` : title;
      toc.appendChild(link);
      return link;
    });

    const setActive = (id) => links.forEach((link) => link.classList.toggle("is-active", link.hash === `#${id}`));
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "-90px 0px -70% 0px" }
    );
    headings.forEach((heading) => observer.observe(heading));
    setActive(headings[0].id);
  }

  // Back-to-top button after the first screen.
  const up = document.getElementById("lg-up");
  if (up) {
    const sync = () => up.classList.toggle("is-visible", window.scrollY > window.innerHeight * 0.8);
    window.addEventListener("scroll", sync, { passive: true });
    up.addEventListener("click", () => window.scrollTo({ top: 0 }));
    sync();
  }
})();
