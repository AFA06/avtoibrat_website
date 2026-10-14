(function () {
  "use strict";

  // Materials are for viewing inside the platform only (Foydalanish shartlari, section 5):
  // pictures can't be saved from the right-click menu or dragged out of the page. On pages marked
  // <html data-protect="strict"> (the test window) text can't be copied and there is no right-click menu at all.
  const strict = document.documentElement.dataset.protect === "strict";
  const isMedia = (target) => Boolean(target.closest && target.closest("img, picture, video, svg, canvas"));

  document.addEventListener("contextmenu", (event) => {
    if (strict || isMedia(event.target)) event.preventDefault();
  });
  document.addEventListener("dragstart", (event) => {
    if (isMedia(event.target)) event.preventDefault();
  });
  if (strict) {
    ["copy", "cut"].forEach((type) => document.addEventListener(type, (event) => event.preventDefault()));
  }
})();
