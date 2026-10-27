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
    answerModalNumber: document.getElementById("answerModalNumber"),
    answerModalQuestion: document.getElementById("answerModalQuestion"),
    answerModalOptions: document.getElementById("answerModalOptions"),
    answerCancelBtn: document.getElementById("answerCancelBtn"),
    answerConfirmBtn: document.getElementById("answerConfirmBtn"),
    finishModal: document.getElementById("finishModal"),
    saveBtn: document.getElementById("saveBtn"),
    finishCancelBtn: document.getElementById("finishCancelBtn"),
    finishConfirmBtn: document.getElementById("finishConfirmBtn"),
    finishForm: document.getElementById(config.finishFormId),
    textDownBtn: document.getElementById("textDownBtn"),
    textUpBtn: document.getElementById("textUpBtn"),
    textScaleValue: document.getElementById("textScaleValue"),
    autoAdvanceInput: document.getElementById("autoAdvanceInput"),
    lang: document.getElementById("examLang"),
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
  const LANGUAGE_STORAGE_KEY = "avtoibrat.exam.language";
  const LANGUAGE_SWAP_MS = 140;
  let currentIndex = 0;
  let language = config.defaultLanguage;
  let pendingSelection = null;
  let submitting = false;
  let autoAdvanceEnabled = true;
  let leaving = false; // set once the test is being finished, so leaving the page is no longer blocked
  const optionOrders = {};
  let currentVoice = null; // the explanation being played, stopped when the question changes

  // Text, answers and voice explanation of a question in the language the student has chosen.
  function contentOf(question) {
    return question.languages[language];
  }

  function shuffledOptionOrder(question) {
    const ids = contentOf(question).answers.map((a) => a.id);
    const previous = optionOrders[question.id];

    // Teachers and admins see every question exactly as stored, answers always in the same place.
    if (ids.length < 2 || config.shuffleOptions === false) {
      optionOrders[question.id] = ids;
      return ids;
    }

    const next = previous ? derangement(orderInLanguage(question)) : fisherYates(ids.slice());
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

  // The order the student already saw, limited to (and completed with) the options of the current language.
  function orderInLanguage(question) {
    const ids = contentOf(question).answers.map((a) => a.id);
    const previous = (optionOrders[question.id] || []).filter((id) => ids.includes(id));
    return previous.concat(ids.filter((id) => !previous.includes(id)));
  }

  function questionOptionOrder(question) {
    if (answered[question.id]) {
      return orderInLanguage(question);
    }
    return shuffledOptionOrder(question);
  }

  // An option like "F1 va F2 javoblar to‘g‘ri" names other options by their original keys.
  // Options move between keys, so the keys in such a text follow the options they point at.
  function linkedText(question, answer) {
    const answers = contentOf(question).answers;
    const order = orderInLanguage(question);
    const pattern = /\bF([1-9])\b/g;
    const keys = [];
    let match;
    while ((match = pattern.exec(answer.text)) !== null) {
      const target = answers[Number(match[1]) - 1];
      if (!target || target.id === answer.id) return answer.text;
      keys.push(order.indexOf(target.id) + 1);
    }
    if (!keys.length) return answer.text;
    keys.sort((x, y) => x - y);
    let next = 0;
    return answer.text.replace(pattern, () => `F${keys[next++]}`);
  }

  function renderCounter() {
    els.counter.textContent = `${strings.questionCounter} ${currentIndex + 1} / ${questions.length}`;
  }

  function renderSaveButton() {
    if (!els.saveBtn) return;
    const saved = Boolean(questions[currentIndex].saved);
    els.saveBtn.classList.toggle("is-saved", saved);
    els.saveBtn.setAttribute("aria-pressed", saved ? "true" : "false");
    const icon = els.saveBtn.querySelector("i");
    icon.className = saved ? "fas fa-bookmark" : "far fa-bookmark";
  }

  function toggleSave() {
    const question = questions[currentIndex];
    fetch(config.toggleSaveUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": config.csrfToken,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ question_id: question.id }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("save_failed");
        return res.json();
      })
      .then((data) => {
        question.saved = data.saved;
        renderSaveButton();
      })
      .catch(() => {});
  }

  if (els.saveBtn) els.saveBtn.addEventListener("click", toggleSave);

  // keepOrder: the same question again in another language, so its options stay where they are.
  function renderQuestion({ keepOrder = false } = {}) {
    const question = questions[currentIndex];
    const content = contentOf(question);
    renderSaveButton();

    els.questionText.textContent = content.text;

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
    } else if (config.logoUrl) {
      const placeholder = document.createElement("div");
      placeholder.className = "exam-noimage";
      placeholder.setAttribute("role", "img");
      placeholder.setAttribute("aria-label", "AvtoIbrat");
      placeholder.style.setProperty("--exam-logo", `url("${config.logoUrl}")`);
      els.imageBox.appendChild(placeholder);
    }

    els.optionsBox.textContent = "";
    if (currentVoice) { currentVoice.pause(); currentVoice = null; }
    const order = keepOrder ? orderInLanguage(question) : questionOptionOrder(question);
    const answersById = {};
    content.answers.forEach((a) => { answersById[a.id] = a; });
    const result = answered[question.id];
    const correctId = result && result.correct[language];

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
      text.textContent = linkedText(question, answer);

      row.appendChild(key);
      row.appendChild(text);

      if (result) {
        row.classList.add("exam-option--locked");
        if (answer.id === correctId) {
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

    if (result && !result.is_correct && content.has_explanation && practice) {
      els.optionsBox.appendChild(explanationPlayer(question));
    }

    renderCounter();
    renderNav();
  }

  // After a mistake: the teacher's short voice explanation. The server only serves it to a student who got it wrong.
  function formatTime(seconds) {
    const whole = Math.max(0, Math.floor(seconds || 0));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  }

  function explanationPlayer(question) {
    const title = config.explanationTitle || "Ustoz tushuntirishi";
    const card = document.createElement("div");
    card.className = "exam-voice";
    card.innerHTML = `
      <button type="button" class="exam-voice__play" aria-label="${title}">
        <i class="ti ti-player-play-filled" aria-hidden="true"></i>
      </button>
      <div class="exam-voice__body">
        <div class="exam-voice__head">
          <span class="exam-voice__title"><i class="ti ti-microphone-2" aria-hidden="true"></i>${title}</span>
          <span class="exam-voice__time">0:00</span>
        </div>
        <input type="range" class="exam-voice__bar" min="0" max="1000" value="0" step="1" aria-label="${title}">
      </div>`;
    const play = card.querySelector(".exam-voice__play");
    const icon = play.querySelector("i");
    const time = card.querySelector(".exam-voice__time");
    const bar = card.querySelector(".exam-voice__bar");

    const audio = new Audio(`${config.explanationUrl.replace(/0\/$/, `${question.id}/`)}?lang=${language}`);
    audio.preload = "metadata";
    const paint = () => {
      const duration = audio.duration || 0;
      const fraction = duration ? audio.currentTime / duration : 0;
      bar.value = Math.round(fraction * 1000);
      bar.style.setProperty("--fill", `${fraction * 100}%`);
      time.textContent = duration ? `${formatTime(audio.currentTime)} / ${formatTime(duration)}` : formatTime(audio.currentTime);
    };
    const setPlaying = (on) => {
      card.classList.toggle("is-playing", on);
      icon.className = on ? "ti ti-player-pause-filled" : "ti ti-player-play-filled";
    };

    play.addEventListener("click", () => {
      if (!audio.paused) { audio.pause(); return; }
      if (audio.ended) audio.currentTime = 0;
      audio.play().catch(() => card.classList.add("is-error"));
    });
    bar.addEventListener("input", () => {
      if (audio.duration) audio.currentTime = (bar.value / 1000) * audio.duration;
      paint();
    });
    audio.addEventListener("loadedmetadata", paint);
    audio.addEventListener("timeupdate", paint);
    audio.addEventListener("play", () => setPlaying(true));
    audio.addEventListener("pause", () => setPlaying(false));
    audio.addEventListener("ended", () => { setPlaying(false); paint(); });
    audio.addEventListener("error", () => card.classList.add("is-error"));
    currentVoice = audio;
    return card;
  }

  // Long sessions (marathon) have hundreds of cells: build them once, then only update classes.
  const MANY_QUESTIONS = 40;
  let navCells = [];

  function buildNav() {
    document.body.classList.toggle("exam--many", questions.length > MANY_QUESTIONS);
    els.navGrid.textContent = "";
    navCells = questions.map((question, index) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "exam-navcell";
      cell.textContent = String(index + 1);
      cell.addEventListener("click", () => goToIndex(index));
      els.navGrid.appendChild(cell);
      return cell;
    });
  }

  function renderNav() {
    if (navCells.length !== questions.length) buildNav();
    navCells.forEach((cell, index) => {
      const result = answered[questions[index].id];
      cell.classList.toggle("exam-navcell--correct", Boolean(result && result.is_correct));
      cell.classList.toggle("exam-navcell--wrong", Boolean(result && !result.is_correct));
      cell.classList.toggle("exam-navcell--current", index === currentIndex);
    });
    keepCurrentCellVisible();
  }

  // Scroll only the navigator itself, never the page, so the current question's cell stays in view.
  function keepCurrentCellVisible() {
    const nav = els.navGrid.closest(".exam-navigator");
    const cell = navCells[currentIndex];
    if (!nav || !cell || nav.scrollHeight <= nav.clientHeight) return;
    const navBox = nav.getBoundingClientRect();
    const cellBox = cell.getBoundingClientRect();
    if (cellBox.top < navBox.top || cellBox.bottom > navBox.bottom) {
      nav.scrollTop += cellBox.top - navBox.top - (nav.clientHeight - cellBox.height) / 2;
    }
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
    renderConfirm();
    openModal(els.answerModal);
  }

  // The confirm dialog repeats the question and every option on its key, the chosen one marked;
  // another option (click or F-key) can be chosen right there, as on the real exam terminal.
  function renderConfirm() {
    const { question, answer } = pendingSelection;
    els.answerModalNumber.textContent = String(currentIndex + 1);
    els.answerModalQuestion.textContent = els.questionText.textContent;
    els.answerModalOptions.textContent = "";
    els.optionsBox.querySelectorAll(".exam-option").forEach((option) => {
      const row = option.cloneNode(true);
      row.className = "exam-confirm__option";
      const selected = row.dataset.answerId === String(answer.id);
      row.classList.toggle("is-selected", selected);
      row.setAttribute("aria-selected", selected ? "true" : "false");
      row.addEventListener("click", () => changeSelection(question, row.dataset.answerId));
      els.answerModalOptions.appendChild(row);
    });
  }

  function changeSelection(question, answerId) {
    const answer = contentOf(question).answers.find((a) => String(a.id) === String(answerId));
    if (!answer) return;
    pendingSelection = { question, answer };
    renderConfirm();
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
          correct: data.correct_answer_ids,
          is_correct: data.is_correct,
        };
        submitting = false;
        const answeredIndex = currentIndex;
        renderQuestion();
        if (data.exam_failed) {
          // Too many mistakes: the server already closed the exam, so show the answer briefly, then the result.
          setTimeout(submitFinish, FEEDBACK_DELAY_MS);
          return;
        }
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
        leaving = true;
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
    leaving = true;
    els.finishForm.submit();
  }

  // ---------- Staying in the test ----------
  // The browser's Back button must not drop the student out of a running test: it opens the
  // «finish the test?» dialog instead. Only finishing (button, timer, failed exam) leaves the page.
  function guardBackButton() {
    const trap = () => history.pushState({ examGuard: true }, "", window.location.href);
    // Chrome ignores history entries added before the student touched the page, so the entry
    // is added on the first touch or key press.
    let armed = false;
    const arm = () => {
      if (armed) return;
      armed = true;
      trap();
    };
    document.addEventListener("pointerdown", arm, { capture: true });
    document.addEventListener("keydown", arm, { capture: true });

    window.addEventListener("popstate", () => {
      if (leaving) return;
      trap();
      closeLightbox();
      if (!anyModalOpen()) openModal(els.finishModal);
    });
    // Second guard (closing the tab, a fast double Back): the browser's own «leave the page?» question.
    window.addEventListener("beforeunload", (e) => {
      if (leaving) return;
      e.preventDefault();
      e.returnValue = "";
    });
  }

  // ---------- Full screen ----------
  // Browsers only allow full screen after a click, tap or key press, so there is no pop-up:
  // the first thing the student does on the page (an answer, a key, a tap) also opens full screen.
  function setupFullscreenStart() {
    if (!document.fullscreenEnabled || document.fullscreenElement || window.top !== window.self) return; // inside the launcher frame the parent is already full screen
    const events = ["pointerdown", "keydown", "touchend"];
    const enter = () => {
      events.forEach((name) => document.removeEventListener(name, enter, true));
      if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {});
    };
    events.forEach((name) => document.addEventListener(name, enter, true));
  }

  function formatTime(totalSeconds) {
    const pad = (n) => String(n).padStart(2, "0");
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return hours ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`;
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
      const key = /^F(\d+)$/.exec(e.key);
      const row = key && els.answerModalOptions.children[parseInt(key[1], 10) - 1];
      if (row) { e.preventDefault(); row.click(); }
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

    if (e.key.toLowerCase() === "s" && els.saveBtn && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      toggleSave();
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

  // ---------- Question language ----------
  // The student can read the questions in any of the languages; the choice is remembered on this device.
  function setupLanguage() {
    const buttons = Array.from(els.lang.querySelectorAll("[data-lang]"));
    const stored = (() => { try { return localStorage.getItem(LANGUAGE_STORAGE_KEY); } catch (e) { return null; } })();
    if (buttons.some((b) => b.dataset.lang === stored)) language = stored;

    const paint = () => {
      const index = buttons.findIndex((b) => b.dataset.lang === language);
      els.lang.style.setProperty("--lang-index", String(Math.max(index, 0)));
      buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === language)));
    };

    let swapTimer = null;
    const choose = (next) => {
      if (next === language) return;
      language = next;
      try { localStorage.setItem(LANGUAGE_STORAGE_KEY, next); } catch (e) { /* storage unavailable: the choice just is not remembered */ }
      document.documentElement.lang = next === "uz-kr" ? "uz-Cyrl" : next;
      paint();
      if (pendingSelection) { pendingSelection = null; closeModal(els.answerModal); }

      // Fade the question out, swap its language, fade back in.
      clearTimeout(swapTimer);
      document.body.classList.add("exam--swapping");
      swapTimer = setTimeout(() => {
        renderQuestion({ keepOrder: true });
        document.body.classList.remove("exam--swapping");
      }, LANGUAGE_SWAP_MS);
    };

    buttons.forEach((button) => button.addEventListener("click", () => choose(button.dataset.lang)));
    paint();
  }

  setupLanguage();
  setupTextSize();
  setupAutoAdvance();
  guardBackButton();
  setupFullscreenStart();
  renderQuestion();
})();
