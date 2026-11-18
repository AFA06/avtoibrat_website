(function () {
  "use strict";

  // Student → Real imtihon: confirm before the exam (and its timer) starts.
  const clearDialog = document.getElementById("rx-clear");
  if (clearDialog) {
    const hide = () => {
      clearDialog.classList.remove("is-open");
      setTimeout(() => clearDialog.open && clearDialog.close(), 250);
    };
    const confirm = clearDialog.querySelector("[data-confirm]");
    document.querySelector("[data-clear-open]").addEventListener("click", () => {
      clearDialog.showModal();
      requestAnimationFrame(() => clearDialog.classList.add("is-open"));
    });
    clearDialog.querySelector("[data-close]").addEventListener("click", hide);
    clearDialog.addEventListener("cancel", (event) => { event.preventDefault(); hide(); });
    clearDialog.addEventListener("click", (event) => { if (event.target === clearDialog) hide(); });
    confirm.addEventListener("click", () => {
      confirm.disabled = true;
      fetch(clearDialog.dataset.url, { method: "POST", headers: { "X-CSRFToken": clearDialog.dataset.csrf } })
        .then((response) => { if (!response.ok) throw new Error(); window.location.reload(); })
        .catch(() => { confirm.disabled = false; });
    });
  }

  const dialog = document.getElementById("rx-confirm");
  if (!dialog) return;
  const go = dialog.querySelector("[data-go]");
  const skipConfirmation = dialog.querySelector("[data-skip-confirmation]");
  const preferenceKey = `avtoibrat.realExam.skipConfirmation.${dialog.dataset.student}`;

  function shouldSkipConfirmation() {
    try {
      return localStorage.getItem(preferenceKey) === "1";
    } catch {
      return false;
    }
  }

  function open(button) {
    ["size", "minutes", "allowed"].forEach((key) => {
      dialog.querySelector(`[data-${key}]`).textContent = button.dataset[key];
    });
    skipConfirmation.checked = false;
    dialog.showModal();
    requestAnimationFrame(() => dialog.classList.add("is-open"));
  }

  function close() {
    dialog.classList.remove("is-open");
    setTimeout(() => dialog.open && !dialog.classList.contains("is-open") && dialog.close(), 250);
  }

  document.querySelectorAll("[data-start]").forEach((button) => {
    button.addEventListener("click", () => {
      if (go.dataset.busy) return;
      go.href = button.dataset.start;
      if (shouldSkipConfirmation()) {
        go.click();
      } else {
        open(button);
      }
    });
  });
  dialog.querySelector("[data-close]").addEventListener("click", close);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    close();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) close();
  });
  go.addEventListener("click", (event) => {
    if (go.dataset.busy) {
      event.preventDefault();
      return;
    }
    go.dataset.busy = "1";
    if (dialog.open && skipConfirmation.checked) {
      try {
        localStorage.setItem(preferenceKey, "1");
      } catch {
        // Start the exam even if browser storage is unavailable.
      }
    }
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      delete go.dataset.busy;
      if (dialog.open) dialog.close();
      dialog.classList.remove("is-open");
    }
  });
})();
