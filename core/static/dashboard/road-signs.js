(function () {
  "use strict";

  const signs = JSON.parse(document.getElementById("rs-signs-data").textContent);
  const $ = (id) => document.getElementById(id);

  const grid = $("rsGrid");
  const search = $("rsSearch");
  const noResults = $("rsNoResults");
  const modal = $("rsModal");
  const modalTitle = $("rsModalTitle");
  const modalImg = $("rsModalImg");
  const modalText = $("rsModalText");
  const lightbox = $("rsLightbox");
  const lightboxImg = $("rsLightboxImg");

  const isOpen = (el) => !el.hidden;

  function syncScrollLock() {
    document.body.classList.toggle("rs-locked", isOpen(modal) || isOpen(lightbox));
  }

  function openModal(index) {
    const sign = signs[index];
    modalTitle.textContent = sign.title;
    modalImg.src = sign.image;
    modalImg.alt = sign.title;
    const hasText = Boolean(sign.description && sign.description.trim());
    modalText.textContent = hasText ? sign.description.trim() : modalText.dataset.empty || "";
    modalText.classList.toggle("is-empty", !hasText);
    modal.hidden = false;
    modal.querySelector(".rs-modal__body").scrollTop = 0;
    syncScrollLock();
    $("rsModalClose").focus();
  }

  function closeModal() {
    modal.hidden = true;
    syncScrollLock();
  }

  function openLightbox(src) {
    lightboxImg.src = src;
    lightbox.hidden = false;
    syncScrollLock();
  }

  function closeLightbox() {
    lightbox.hidden = true;
    syncScrollLock();
  }

  grid.addEventListener("click", (e) => {
    const zoom = e.target.closest(".rs-zoom");
    if (zoom) { openLightbox(signs[zoom.dataset.index].image); return; }
    const open = e.target.closest(".rs-open");
    if (open) openModal(open.dataset.index);
  });

  $("rsModalClose").addEventListener("click", closeModal);
  $("rsModalImgBtn").addEventListener("click", () => openLightbox(modalImg.src));
  // Only a click on the dark backdrop closes; clicks inside the card or on the picture do not.
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
  lightbox.addEventListener("click", (e) => { if (e.target === lightbox) closeLightbox(); });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (isOpen(lightbox)) closeLightbox();
    else if (isOpen(modal)) closeModal();
  });

  // Search by sign number or name; all signs stay on one scrolling page.
  const cards = Array.from(grid.children);
  function normalize(text) {
    return text.toLowerCase().replace(/[ʻʼ’‘`´']/g, "'").trim();
  }
  cards.forEach((card) => { card.dataset.search = normalize(card.dataset.search); });

  search.addEventListener("input", () => {
    const words = normalize(search.value).split(/\s+/).filter(Boolean);
    let visible = 0;
    cards.forEach((card) => {
      const match = words.every((w) => card.dataset.search.includes(w));
      card.hidden = !match;
      if (match) visible += 1;
    });
    noResults.hidden = visible > 0;
  });
})();
