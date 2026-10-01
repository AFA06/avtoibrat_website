(function () {
  "use strict";

  // --- Student list: reveal / copy passwords, confirm destructive actions ---
  document.querySelectorAll("[data-reveal]").forEach((btn) => {
    const code = btn.parentElement.querySelector("code");
    btn.addEventListener("click", () => {
      const hidden = code.textContent.includes("•");
      code.textContent = hidden ? code.dataset.password : "••••••••";
      btn.querySelector("i").className = hidden ? "fas fa-eye-slash" : "fas fa-eye";
    });
  });

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const code = btn.parentElement.querySelector("code");
      navigator.clipboard.writeText(code.dataset.password).then(() => {
        const icon = btn.querySelector("i");
        icon.className = "fas fa-check";
        setTimeout(() => (icon.className = "far fa-copy"), 1200);
      });
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // Row action menus: one open at a time, closed by outside click or Escape
  const menus = document.querySelectorAll(".sd-dd");
  const closeMenus = (except) => menus.forEach((m) => m !== except && m.classList.remove("is-open"));
  menus.forEach((menu) => {
    menu.querySelector("[data-menu]").addEventListener("click", (event) => {
      event.stopPropagation();
      closeMenus(menu);
      menu.classList.toggle("is-open");
    });
  });
  document.addEventListener("click", () => closeMenus());
  document.addEventListener("keydown", (event) => event.key === "Escape" && closeMenus());

  // Live filter for pick lists (e.g. choosing students to add to a group)
  document.querySelectorAll("[data-filter-input]").forEach((input) => {
    const items = document.querySelectorAll(input.dataset.filterInput);
    input.addEventListener("input", () => {
      const needle = input.value.trim().toLowerCase();
      items.forEach((item) => (item.hidden = !item.textContent.toLowerCase().includes(needle)));
    });
  });
  document.querySelectorAll("[data-toggle-panel]").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = document.getElementById(button.dataset.togglePanel);
      panel.hidden = !panel.hidden;
      if (!panel.hidden) panel.querySelector("input[type=search]")?.focus();
    });
  });

  // Group schedule: day presets and "end = start + 2h"
  document.querySelectorAll("[data-days]").forEach((preset) => {
    preset.addEventListener("click", () => {
      const days = preset.dataset.days.split(",");
      document.querySelectorAll(".sd-day input").forEach((box) => (box.checked = days.includes(box.value)));
    });
  });
  const start = document.getElementById("id_lesson_start");
  const end = document.getElementById("id_lesson_end");
  if (start && end) {
    start.addEventListener("change", () => {
      if (!start.value || (end.value && end.value > start.value)) return;
      const [h, m] = start.value.split(":").map(Number);
      const value = `${String(h + 2).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      if ([...end.options].some((o) => o.value === value)) end.value = value;
    });
  }

  // --- Student form: 99-999-99-99 phone mask ---
  const phone = document.querySelector("[data-phone-mask]");
  if (phone) {
    const format = (value) => {
      let digits = value.replace(/\D/g, "");
      if (digits.startsWith("998") && digits.length > 9) digits = digits.slice(3);
      digits = digits.slice(0, 9);
      return [digits.slice(0, 2), digits.slice(2, 5), digits.slice(5, 7), digits.slice(7, 9)]
        .filter(Boolean).join("-");
    };
    phone.addEventListener("input", () => (phone.value = format(phone.value)));
  }

  // --- Student form: password generator ---
  const generate = document.getElementById("generate-password");
  if (generate) {
    const form = generate.closest("form");
    let clicks = 0;
    generate.addEventListener("click", async () => {
      const params = new URLSearchParams({
        first_name: form.elements.first_name.value,
        birth_date: form.elements.birth_date ? form.elements.birth_date.value : "",
        again: clicks++ ? "1" : "0",
      });
      const response = await fetch(`${form.dataset.suggestUrl}?${params}`);
      form.elements.password.value = (await response.json()).password;
    });
  }
})();
