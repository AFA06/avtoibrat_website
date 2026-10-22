(function () {
  "use strict";

  // --- Answer rows: add, remove, renumber keys and radio values ---
  function renumber(list) {
    list.querySelectorAll(".qs-answer").forEach((row, index) => {
      row.querySelector(".qs-key").textContent = `F${index + 1}`;
      row.querySelector("input[type=radio]").value = index;
    });
  }

  document.querySelectorAll("[data-add]").forEach((button) => {
    button.addEventListener("click", () => {
      const list = document.querySelector(`[data-list="${button.dataset.add}"]`);
      if (list.children.length >= Number(list.dataset.limit)) return;
      const row = list.lastElementChild.cloneNode(true);
      row.querySelectorAll("input[type=text]").forEach((input) => (input.value = ""));
      row.querySelector("input[type=hidden]").value = "";
      row.querySelector("input[type=radio]").checked = false;
      list.appendChild(row);
      renumber(list);
      row.querySelector("input[type=text]").focus();
      button.disabled = list.children.length >= Number(list.dataset.limit);
    });
  });

  document.querySelectorAll("[data-list]").forEach((list) => {
    list.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-remove]");
      if (!remove) return;
      const row = remove.closest(".qs-answer");
      if (list.children.length > 2) {
        row.remove();
      } else {
        row.querySelectorAll("input[type=text]").forEach((input) => (input.value = ""));
        row.querySelector("input[type=radio]").checked = false;
      }
      renumber(list);
      document.querySelector(`[data-add="${list.dataset.list}"]`).disabled = false;
    });
  });

  // --- Topic checkboxes: quick filter ---
  const filter = document.querySelector("[data-topic-filter]");
  if (filter) {
    filter.addEventListener("input", () => {
      const needle = filter.value.trim().toLowerCase();
      document.querySelectorAll("[data-topic-list] .qs-check").forEach((box) => {
        box.hidden = needle && !box.textContent.toLowerCase().includes(needle);
      });
    });
  }

  // --- The main topic needs no second tick among the extra ones ---
  const main = document.getElementById("id_mavzu");
  const boxes = Array.from(document.querySelectorAll("[data-topic-list] input[type=checkbox]"));
  function syncMain() {
    boxes.forEach((box) => {
      const same = main && box.value === main.value;
      if (same) box.checked = false;
      box.disabled = Boolean(same);
      box.closest(".qs-check").style.opacity = same ? ".45" : "";
    });
  }
  if (main) {
    main.addEventListener("change", syncMain);
    syncMain();
  }

  // --- Show how many questions the chosen bilet already has ---
  const bilet = document.getElementById("id_kategoriya");
  const note = document.getElementById("bilet-note");
  const counts = JSON.parse(document.getElementById("bilet-counts").textContent);
  function showCount() {
    const total = counts[bilet.value] || 0;
    const editing = location.pathname.match(/\/questions\/\d+\/$/);
    note.textContent = `Bu biletda hozir ${total} ta savol bor.`;
    note.classList.toggle("qs-bilet-full", total >= 20 && !editing);
    if (total >= 20 && !editing) note.textContent += " Standart bilet 20 ta savoldan iborat, yangisi uni 21 ta qiladi.";
  }
  if (bilet && note) {
    bilet.addEventListener("change", showCount);
    showCount();
  }
})();
