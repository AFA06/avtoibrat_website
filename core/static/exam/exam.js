(function () {
  "use strict";

  const questions = JSON.parse(document.getElementById("exam-questions-data").textContent);
  const answered = JSON.parse(document.getElementById("exam-answered-data").textContent);
  let remainingSeconds = JSON.parse(document.getElementById("exam-remaining-seconds").textContent);
  const strings = JSON.parse(document.getElementById("exam-strings").textContent);
  const config = window.EXAM_CONFIG;

  const els = {
    counter: document.getElementById("examCounter"),
    timer: document.getElementById("examTimer"),
    timerValue: document.getElementById("examTimerValue"),
    fullscreenBtn: document.getElementById("fullscreenBtn"),
    finishBtn: document.getElementById("finishBtn"),
    questionText: document.getElementById("examQuestionText"),
    imageBox: document.getElementById("examImageBox"),
    optionsBox: document.getElementById("examOptions"),
    navGrid: document.getElementById("examNavGrid"),
    prevBtn: document.getElementById("prevBtn"),
    nextBtn: document.getElementById("nextBtn"),
    answerModal: document.getElementById("answerModal"),
    answerModalText: document.getElementById("answerModalText"),
    answerCancelBtn: document.getElementById("answerCancelBtn"),
    answerConfirmBtn: document.getElementById("answerConfirmBtn"),
    finishModal: document.getElementById("finishModal"),
    finishCancelBtn: document.getElementById("finishCancelBtn"),
    finishConfirmBtn: document.getElementById("finishConfirmBtn"),
    finishForm: document.getElementById(config.finishFormId),
    textDownBtn: document.getElementById("textDownBtn"),
    textUpBtn: document.getElementById("textUpBtn"),
    textScaleValue: document.getElementById("textScaleValue"),
    autoAdvanceInput: document.getElementById("autoAdvanceInput"),
  };

  const practice = Boolean(config.practice);

  const FEEDBACK_DELAY_MS = 1200;
  const TEXT_SIZE = {
    minLevel: -9,
    maxLevel: 15,
    stepUp: 0.05,
    stepDown: 0.03,
    storageKey: "avtoibrat.exam.textLevel",
  };
  const AUTO_ADVANCE_STORAGE_KEY = "avtoibrat.exam.autoAdvance";
  let currentIndex = 0;
  let pendingSelection = null;
  let submitting = false;
  let autoAdvanceEnabled = true;
  const optionOrders = {};

  function shuffledOptionOrder(question) {
    const ids = question.answers.map((a) => a.id);
    const previous = optionOrders[question.id];

    if (ids.length < 2) {
      optionOrders[question.id] = ids;
      return ids;
    }

    const next = previous ? derangement(previous) : fisherYates(ids.slice());
    optionOrders[question.id] = next;
    return next;
  }

  // Every option must land on a new key so students re-read instead of memorising positions.
  function derangement(previous) {
    for (let attempt = 0; attempt < 100; attempt++) {
      const candidate = fisherYates(previous.slice());
      if (candidate.every((id, i) => id !== previous[i])) return candidate;
    }
    return previous.slice(1).concat(previous[0]);
  }

  function fisherYates(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function questionOptionOrder(question) {
    if (answered[question.id]) {
      return optionOrders[question.id] || question.answers.map((a) => a.id);
    }
    return shuffledOptionOrder(question);
  }

  function renderCounter() {
    els.counter.textContent = `${strings.questionCounter} ${currentIndex + 1} / ${questions.length}`;
  }

  function renderQuestion() {
    const question = questions[currentIndex];

    els.questionText.textContent = question.text;

    els.imageBox.textContent = "";
    if (question.image) {
      const img = document.createElement("img");
      img.src = question.image;
      img.alt = "";
      const frame = document.createElement("div");
      frame.className = "exam-zoomable";
      frame.tabIndex = 0;
      frame.setAttribute("role", "button");
      frame.appendChild(img);
      const hint = document.createElement("span");
      hint.className = "exam-zoomable__key";
      hint.textContent = "F";
      frame.appendChild(hint);
      frame.addEventListener("click", () => openLightbox(question.image));
      els.imageBox.appendChild(frame);
    }

    els.optionsBox.textContent = "";
    const order = questionOptionOrder(question);
    const answersById = {};
    question.answers.forEach((a) => { answersById[a.id] = a; });
    const result = answered[question.id];

    order.forEach((answerId, position) => {
      const answer = answersById[answerId];
      const row = document.createElement("div");
      row.className = "exam-option";
      row.dataset.answerId = String(answer.id);

      const key = document.createElement("span");
      key.className = "exam-option__key";
      key.textContent = `F${position + 1}`;

      const text = document.createElement("span");
      text.className = "exam-option__text";
      text.textContent = answer.text;

      row.appendChild(key);
      row.appendChild(text);

      if (result) {
        row.classList.add("exam-option--locked");
        if (answer.id === result.correct) {
          row.classList.add("exam-option--correct");
        }
        if (answer.id === result.selected && !result.is_correct) {
          row.classList.add("exam-option--wrong");
        }
      } else {
        row.addEventListener("click", () => selectOption(question, answer));
      }

      els.optionsBox.appendChild(row);
    });

    renderCounter();
    renderNav();
  }

  function renderNav() {
    els.navGrid.textContent = "";
    questions.forEach((question, index) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "exam-navcell";
      cell.textContent = String(index + 1);

      const result = answered[question.id];
      if (result) {
        cell.classList.add(result.is_correct ? "exam-navcell--correct" : "exam-navcell--wrong");
      }
      if (index === currentIndex) {
        cell.classList.add("exam-navcell--current");
      }

      cell.addEventListener("click", () => goToIndex(index));
      els.navGrid.appendChild(cell);
    });
  }

  function goToIndex(index) {
    if (index < 0 || index >= questions.length || index === currentIndex) return;
    currentIndex = index;
    renderQuestion();
  }

  function selectOption(question, answer) {
    if (practice) {
      submitAnswer(question, answer);
      return;
    }
    pendingSelection = { question, answer };
    els.answerModalText.textContent = answer.text;
    openModal(els.answerModal);
  }

  function confirmSelection() {
    if (!pendingSelection) return;
    const { question, answer } = pendingSelection;
    pendingSelection = null;
    closeModal(els.answerModal);
    submitAnswer(question, answer);
  }

  function submitAnswer(question, answer) {
    if (submitting) return;
    submitting = true;
    fetch(config.submitUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": config.csrfToken,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        session_id: config.sessionId,
        question_id: question.id,
        answer_id: answer.id,
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("submit_failed");
        return res.json();
      })
      .then((data) => {
        answered[question.id] = {
          selected: answer.id,
          correct: data.correct_answer_id,
          is_correct: data.is_correct,
        };
        submitting = false;
        const answeredIndex = currentIndex;
        renderQuestion();
        if (questions.every((q) => answered[q.id])) {
          // Everything is answered: offer to finish, same dialog as the Yakunlash button.
          setTimeout(() => { closeLightbox(); openModal(els.finishModal); }, FEEDBACK_DELAY_MS);
          return;
        }
        if (practice && !autoAdvanceEnabled) return;
        setTimeout(() => {
          if (currentIndex === answeredIndex && !anyModalOpen()) {
            goToIndex(currentIndex + 1);
          }
        }, FEEDBACK_DELAY_MS);
      })
      .catch(() => {
        window.location.reload();
      });
  }

  function openModal(modal) {
    modal.classList.add("exam-modal--open");
  }

  function closeModal(modal) {
    modal.classList.remove("exam-modal--open");
  }

  function isModalOpen(modal) {
    return Boolean(modal) && modal.classList.contains("exam-modal--open");
  }

  function anyModalOpen() {
    return isModalOpen(els.answerModal) || isModalOpen(els.finishModal);
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }

  function submitFinish() {
    els.finishForm.submit();
  }

  function formatTime(totalSeconds) {
    const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
    const s = String(totalSeconds % 60).padStart(2, "0");
    return `${m}:${s}`;
  }

  function tickTimer() {
    els.timerValue.textContent = formatTime(Math.max(remainingSeconds, 0));
    els.timer.classList.toggle("exam-timer--danger", remainingSeconds <= 60);

    if (remainingSeconds <= 0) {
      clearInterval(timerHandle);
      submitFinish();
      return;
    }
    remainingSeconds -= 1;
  }

  const timerHandle = setInterval(tickTimer, 1000);
  tickTimer();

  els.prevBtn.addEventListener("click", () => goToIndex(currentIndex - 1));
  els.nextBtn.addEventListener("click", () => goToIndex(currentIndex + 1));
  els.fullscreenBtn.addEventListener("click", toggleFullscreen);
  els.finishBtn.addEventListener("click", () => openModal(els.finishModal));

  if (!practice) {
    els.answerCancelBtn.addEventListener("click", () => {
      pendingSelection = null;
      closeModal(els.answerModal);
    });
    els.answerConfirmBtn.addEventListener("click", confirmSelection);
  }

  els.finishCancelBtn.addEventListener("click", () => closeModal(els.finishModal));
  els.finishConfirmBtn.addEventListener("click", submitFinish);

  document.addEventListener("keydown", (e) => {
    if (isModalOpen(els.answerModal)) {
      if (e.key === "Enter") { e.preventDefault(); confirmSelection(); }
      if (e.key === "Escape") { e.preventDefault(); pendingSelection = null; closeModal(els.answerModal); }
      return;
    }

    if (isModalOpen(els.finishModal)) {
      if (e.key === "Enter") { e.preventDefault(); submitFinish(); }
      if (e.key === "Escape") { e.preventDefault(); closeModal(els.finishModal); }
      return;
    }

    if (lightboxEl && lightboxEl.classList.contains("is-open")) {
      if (e.key === "Escape" || e.key.toLowerCase() === "f") { e.preventDefault(); closeLightbox(); }
      return;
    }

    if (e.key.toLowerCase() === "f" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const img = els.imageBox.querySelector("img");
      if (img) { e.preventDefault(); openLightbox(img.src); }
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      openModal(els.finishModal);
      return;
    }

    if (e.key === "ArrowLeft") { e.preventDefault(); goToIndex(currentIndex - 1); return; }
    if (e.key === "ArrowRight") { e.preventDefault(); goToIndex(currentIndex + 1); return; }

    if (e.key.toLowerCase() === "l") { e.preventDefault(); toggleFullscreen(); return; }

    const fMatch = /^F(\d+)$/.exec(e.key);
    if (fMatch && !anyModalOpen()) {
      e.preventDefault();
      const position = parseInt(fMatch[1], 10) - 1;
      const option = els.optionsBox.children[position];
      if (option && !option.classList.contains("exam-option--locked")) {
        option.click();
      }
    }
  });

  function textScale(level) {
    return 1 + level * (level >= 0 ? TEXT_SIZE.stepUp : TEXT_SIZE.stepDown);
  }

  function readTextLevel() {
    try {
      const stored = parseInt(window.localStorage.getItem(TEXT_SIZE.storageKey), 10);
      return Number.isNaN(stored) ? 0 : Math.min(Math.max(stored, TEXT_SIZE.minLevel), TEXT_SIZE.maxLevel);
    } catch (error) {
      return 0;
    }
  }

  function saveTextLevel(level) {
    try {
      window.localStorage.setItem(TEXT_SIZE.storageKey, String(level));
    } catch (error) {
      // Storage can be blocked; the size still applies for this page.
    }
  }

  function setupTextSize() {
    if (!els.textUpBtn || !els.textDownBtn) return;
    let level = readTextLevel();

    const apply = () => {
      const scale = textScale(level);
      document.documentElement.style.setProperty("--exam-text-scale", scale.toFixed(2));
      els.textScaleValue.textContent = `${Math.round(scale * 100)}%`;
      els.textUpBtn.disabled = level >= TEXT_SIZE.maxLevel;
      els.textDownBtn.disabled = level <= TEXT_SIZE.minLevel;
    };

    const change = (step) => {
      level = Math.min(Math.max(level + step, TEXT_SIZE.minLevel), TEXT_SIZE.maxLevel);
      saveTextLevel(level);
      apply();
    };

    els.textUpBtn.addEventListener("click", () => change(1));
    els.textDownBtn.addEventListener("click", () => change(-1));
    apply();
  }

  function readAutoAdvance() {
    try {
      // On by default; only an explicit "0" (user switched it off) disables it.
      return window.localStorage.getItem(AUTO_ADVANCE_STORAGE_KEY) !== "0";
    } catch (error) {
      return true;
    }
  }

  function saveAutoAdvance(enabled) {
    try {
      window.localStorage.setItem(AUTO_ADVANCE_STORAGE_KEY, enabled ? "1" : "0");
    } catch (error) {
      // Storage can be blocked; the choice just won't be remembered.
    }
  }

  function setupAutoAdvance() {
    if (!els.autoAdvanceInput) return;
    autoAdvanceEnabled = readAutoAdvance();
    els.autoAdvanceInput.checked = autoAdvanceEnabled;
    els.autoAdvanceInput.addEventListener("change", () => {
      autoAdvanceEnabled = els.autoAdvanceInput.checked;
      saveAutoAdvance(autoAdvanceEnabled);
    });
  }

  let lightboxEl = null;

  function ensureLightbox() {
    if (lightboxEl) return lightboxEl;
    lightboxEl = document.createElement("div");
    lightboxEl.className = "exam-lightbox";
    lightboxEl.innerHTML = '<img class="exam-lightbox__img" alt="">';
    // Only a click on the dark backdrop closes it; clicks on the picture do nothing.
    lightboxEl.addEventListener("click", (e) => {
      if (e.target === lightboxEl) closeLightbox();
    });
    document.body.appendChild(lightboxEl);
    return lightboxEl;
  }

  function openLightbox(src) {
    if (anyModalOpen()) return;
    const box = ensureLightbox();
    box.querySelector("img").src = src;
    box.classList.add("is-open");
  }

  function closeLightbox() {
    if (lightboxEl) lightboxEl.classList.remove("is-open");
  }

  setupTextSize();
  setupAutoAdvance();
  renderQuestion();
})();
