(function () {
  "use strict";

  // Image picker: show a preview straight away, also when a file is dropped on the box.
  document.querySelectorAll("[data-image-input]").forEach((input) => {
    const field = input.closest(".sd-field");
    const drop = field.querySelector(".rsa-drop");
    const preview = field.querySelector("[data-image-preview]");
    const hint = field.querySelector("[data-image-hint]");
    const change = field.querySelector("[data-image-change]");

    const show = () => {
      const file = input.files[0];
      if (!file) return;
      preview.src = URL.createObjectURL(file);
      preview.hidden = change.hidden = false;
      hint.hidden = true;
    };
    input.addEventListener("change", show);

    ["dragenter", "dragover"].forEach((name) =>
      drop.addEventListener(name, (event) => { event.preventDefault(); drop.classList.add("is-over"); }));
    ["dragleave", "drop"].forEach((name) =>
      drop.addEventListener(name, () => drop.classList.remove("is-over")));
    drop.addEventListener("drop", (event) => {
      event.preventDefault();
      if (!event.dataTransfer.files.length) return;
      input.files = event.dataTransfer.files;
      show();
    });
  });
})();
