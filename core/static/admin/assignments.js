(function () {
  "use strict";

  // Task form: the group picker only matters when the task is for a single group.
  const form = document.getElementById("assignment-form");
  if (!form) return;
  const groupField = document.getElementById("group-field");
  const radios = form.querySelectorAll("input[name=audience]");

  const sync = () => {
    const forGroup = form.querySelector("input[name=audience]:checked")?.value === "group";
    groupField.hidden = !forGroup;
  };
  radios.forEach((radio) => radio.addEventListener("change", sync));
  sync();
})();
