(function () {
  "use strict";

  // The start button stays off until a range is picked.
  const form = document.getElementById("marathon-form");
  const start = document.getElementById("marathon-start");
  if (!form || !start) return;

  const sync = () => (start.disabled = !form.querySelector("input[name=size]:checked"));
  form.addEventListener("change", sync);
  sync();
})();
