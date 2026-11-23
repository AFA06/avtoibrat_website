(function () {
  "use strict";
  const form = document.getElementById("assignment-form");
  if (!form) return;
  const value = (name) => form.querySelector(`input[name="${name}"]:checked`)?.value;
  const pane = (id, shown) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.hidden = !shown;
    el.querySelectorAll("input, select, textarea, button").forEach((input) => { input.disabled = !shown; });
  };
  const sync = () => {
    const audience = value("audience"), scope = value("recipient_scope"), kind = value("content_type");
    pane("group-field", audience === "group");
    if (!form.querySelector('[name="content_type"]')) return;
    pane("express-settings", audience === "express");
    pane("express-picker", audience === "express" && scope === "selected");
    const hint = document.getElementById("express-all-hint");
    hint.hidden = scope === "selected";
    pane("individual-picker", audience === "individual");
    pane("bilets-picker", kind === "bilet");
    pane("topics-picker", kind === "topic");
    const count = form.querySelectorAll(`input[name="${kind === "topic" ? "topics" : "bilets"}"]:checked`).length;
    form.querySelector("[data-content-summary]").textContent = count ? `${count} ta ${kind === "topic" ? "mavzu" : "bilet"} tanlandi` : "Testlarni tanlang";
  };
  form.querySelectorAll("[data-picker]").forEach((picker) => {
    const search = picker.querySelector("[data-picker-search]");
    const rows = [...picker.querySelectorAll("[data-choice]")];
    const updateCount = () => { picker.querySelector("[data-picker-count]").textContent = `Tanlandi: ${picker.querySelectorAll('input[type="checkbox"]:checked').length}`; };
    search.addEventListener("input", () => {
      const query = search.value.trim().toLocaleLowerCase();
      rows.forEach((row) => { row.hidden = !row.textContent.toLocaleLowerCase().includes(query); });
      picker.querySelector("[data-no-matches]").hidden = !rows.length || rows.some((row) => !row.hidden);
    });
    picker.querySelector("[data-select-visible]").addEventListener("click", () => {
      rows.filter((row) => !row.hidden).forEach((row) => { row.querySelector("input").checked = true; });
      updateCount(); sync();
    });
    picker.querySelector("[data-clear-selection]").addEventListener("click", () => {
      rows.forEach((row) => { row.querySelector("input").checked = false; });
      updateCount(); sync();
    });
    picker.addEventListener("change", updateCount);
    updateCount();
  });
  form.addEventListener("change", sync);
  sync();
  const error = form.querySelector(".has-error") || document.getElementById("form-errors");
  if (error) error.scrollIntoView({block: "center"});
})();
