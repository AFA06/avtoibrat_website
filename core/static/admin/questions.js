(function () {
  "use strict";

  // --- Answer rows: add, remove, renumber keys and radio values ---
  function renumber(list) {
    list.querySelectorAll(".qs-answer").forEach((row, index) => {
      row.querySelector(".qs-key").textContent = `F${index + 1}`;
      row.querySelector("input[type=radio]").value = index;
    });
    refresh(list);
  }

  // What is missing in an answer list: at least two filled rows and one of them marked «To‘g‘ri».
  function problemOf(list) {
    const rows = Array.from(list.querySelectorAll(".qs-answer"));
    const filled = rows.filter((row) => Array.from(row.querySelectorAll("input[type=text]")).some((i) => i.value.trim()));
    const correct = rows.findIndex((row) => row.querySelector("input[type=radio]").checked);
    if (filled.length < 2) return "Kamida 2 ta javob yozing.";
    if (correct < 0 || !filled.includes(rows[correct])) return "To‘g‘ri javob qatoridagi «To‘g‘ri» tugmasini bosing.";
    return "";
  }

  function refresh(list) {
    const status = document.querySelector(`[data-status="${list.dataset.list}"]`);
    const rows = Array.from(list.querySelectorAll(".qs-answer"));
    const correct = rows.findIndex((row) => row.querySelector("input[type=radio]").checked);
    const problem = problemOf(list);
    list.classList.remove("has-problem");
    status.className = `qs-status ${problem ? "is-warn" : "is-ok"}`;
    status.textContent = problem || `✓ To‘g‘ri javob: F${correct + 1}`;
  }

  document.querySelectorAll("[data-list]").forEach((list) => {
    list.addEventListener("input", () => refresh(list));
    list.addEventListener("change", () => refresh(list));
    refresh(list);
  });

  const form = document.getElementById("question-form");
  if (form) {
    form.addEventListener("submit", (event) => {
      const broken = Array.from(document.querySelectorAll("[data-list]")).filter((list) => problemOf(list));
      if (!broken.length) return;
      event.preventDefault();
      broken.forEach((list) => list.classList.add("has-problem"));
      broken[0].scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  // --- List: changing only a question's picture uploads it straight away ---
  document.querySelectorAll("[data-quick-picture]").forEach((input) => {
    input.addEventListener("change", () => {
      if (!input.files.length) return;
      const pic = input.closest(".qs-pic");
      pic.classList.add("is-busy");
      pic.submit();
    });
  });

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

  // --- Voice explanations: pick a file or record with the microphone (stops by itself after 20 s) ---
  const MAX_SECONDS = 20;
  document.querySelectorAll("[data-voice]").forEach((box) => {
    const input = box.querySelector("[data-audio-input]");
    const player = box.querySelector("[data-voice-player]");
    const status = box.querySelector("[data-voice-status]");
    const recordButton = box.querySelector("[data-record]");
    const show = (url, text) => {
      player.src = url;
      player.hidden = false;
      status.textContent = text;
    };
    input.addEventListener("change", () => {
      if (input.files[0]) show(URL.createObjectURL(input.files[0]), `Tanlandi: ${input.files[0].name}`);
    });
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      recordButton.hidden = true;
      return;
    }
    let recorder = null;
    let timer = null;
    const stop = () => { clearTimeout(timer); if (recorder && recorder.state !== "inactive") recorder.stop(); };
    recordButton.addEventListener("click", async () => {
      if (recorder && recorder.state === "recording") return stop();
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (error) {
        status.textContent = "Mikrofonga ruxsat berilmadi.";
        return;
      }
      const chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.addEventListener("dataavailable", (event) => chunks.push(event.data));
      recorder.addEventListener("stop", () => {
        stream.getTracks().forEach((track) => track.stop());
        recordButton.classList.remove("is-recording");
        recordButton.querySelector("span").textContent = "Ovoz yozish";
        const type = recorder.mimeType || "audio/webm";
        const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        const file = new File(chunks, `tushuntirish.${extension}`, { type });
        const transfer = new DataTransfer();
        transfer.items.add(file);
        input.files = transfer.files;
        show(URL.createObjectURL(file), "Yozildi — saqlash tugmasini bosing.");
      });
      recorder.start();
      recordButton.classList.add("is-recording");
      recordButton.querySelector("span").textContent = "To‘xtatish";
      status.textContent = `Yozilmoqda… (eng ko‘pi bilan ${MAX_SECONDS} soniya)`;
      timer = setTimeout(stop, MAX_SECONDS * 1000);
    });
  });

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
