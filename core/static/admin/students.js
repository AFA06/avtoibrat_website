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
        birth_date: form.elements.birth_date.value,
        again: clicks++ ? "1" : "0",
      });
      const response = await fetch(`${form.dataset.suggestUrl}?${params}`);
      form.elements.password.value = (await response.json()).password;
    });
  }
})();
