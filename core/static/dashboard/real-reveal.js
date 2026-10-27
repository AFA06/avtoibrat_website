(function () {
  "use strict";

  // Real exam result reveal: a short, cinematic "verdict" shown once after the exam, replayable by a button.
  const root = document.getElementById("reveal");
  const dataNode = document.getElementById("reveal-data");
  if (!root || !dataNode) return;
  const d = JSON.parse(dataNode.textContent);
  const t = d.t;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const seenKey = `ai.reveal.${d.id}`;
  const muteKey = "ai.reveal.mute";

  const store = {
    get: (key) => { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set: (key, value) => { try { localStorage.setItem(key, value); } catch (e) { /* private mode */ } },
  };
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const rand = (min, max) => min + Math.random() * (max - min);
  const el = (tag, className, html) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (html !== undefined) node.innerHTML = html;
    return node;
  };
  const esc = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fill = (text) => esc(text.replace("%(name)s", d.name));

  // ---------- Sound (synthesised, no files) ----------
  let audio = null;
  let muted = store.get(muteKey) === "1";
  function ctx() {
    if (!audio) {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (Context) audio = new Context();
    }
    if (audio && audio.state === "suspended") audio.resume();
    return audio;
  }
  function tone(freq, duration, { type = "sine", volume = 0.12, delay = 0, slideTo = null } = {}) {
    const c = muted ? null : ctx();
    if (!c) return;
    const start = c.currentTime + delay;
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, start);
    if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, start + duration);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(volume, start + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    osc.connect(gain).connect(c.destination);
    osc.start(start);
    osc.stop(start + duration + 0.05);
  }
  function noise(duration, { volume = 0.2, delay = 0, freq = 1000, q = 1, type = "bandpass" } = {}) {
    const c = muted ? null : ctx();
    if (!c) return;
    const start = c.currentTime + delay;
    const buffer = c.createBuffer(1, Math.ceil(c.sampleRate * duration), c.sampleRate);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;
    const source = c.createBufferSource();
    const filter = c.createBiquadFilter();
    const gain = c.createGain();
    source.buffer = buffer;
    filter.type = type;
    filter.frequency.value = freq;
    filter.Q.value = q;
    gain.gain.setValueAtTime(volume, start);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    source.connect(filter).connect(gain).connect(c.destination);
    source.start(start);
  }
  const sounds = {
    tick: (ok, step) => tone(ok ? 520 + step * 14 : 180, 0.07, { type: ok ? "triangle" : "square", volume: ok ? 0.07 : 0.06 }),
    heartbeat: () => { tone(60, 0.18, { volume: 0.35, slideTo: 40 }); tone(60, 0.18, { volume: 0.3, slideTo: 40, delay: 0.22 }); },
    fanfare: () => {
      [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.28, { type: "triangle", volume: 0.14, delay: i * 0.11 }));
      [523, 659, 784, 1047, 1319].forEach((f) => tone(f, 1.1, { type: "sine", volume: 0.07, delay: 0.5 }));
    },
    pop: () => tone(900, 0.12, { type: "square", volume: 0.05, slideTo: 200 }),
    fail: () => {
      [392, 370, 349, 311].forEach((f, i) => tone(f, 0.38, { type: "sawtooth", volume: 0.09, delay: i * 0.28, slideTo: f * 0.93 }));
      tone(70, 0.7, { type: "sine", volume: 0.4, slideTo: 38, delay: 0.1 });
    },
    screech: () => {
      noise(0.95, { volume: 0.22, freq: 2600, q: 8 });
      tone(1900, 0.9, { type: "sawtooth", volume: 0.035, slideTo: 1450 });
    },
    crash: () => {
      noise(0.9, { volume: 0.9, freq: 900, q: 0.4, type: "lowpass" });
      tone(55, 0.6, { volume: 0.6, slideTo: 30 });
      for (let i = 0; i < 9; i++) tone(rand(2600, 5200), 0.12, { type: "triangle", volume: 0.04, delay: 0.08 + i * 0.05 }); // glass
    },
    restart: () => { tone(110, 0.5, { type: "sawtooth", volume: 0.07, slideTo: 260 }); tone(330, 0.25, { type: "triangle", volume: 0.1, delay: 0.5 }); tone(494, 0.35, { type: "triangle", volume: 0.1, delay: 0.7 }); },
  };

  // ---------- Particles ----------
  let canvas;
  let g;
  let particles = [];
  let frame = 0;
  let last = 0;
  const COLORS = ["#fbbf24", "#34d399", "#60a5fa", "#f472b6", "#a78bfa", "#fb923c", "#ffffff"];

  function sizeCanvas() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = innerWidth * ratio;
    canvas.height = innerHeight * ratio;
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
  }
  function add(p) { particles.push(Object.assign({ x: 0, y: 0, vx: 0, vy: 0, g: 0, drag: 1, life: 0, max: 1, size: 4, color: "#fff", shape: "dot", rot: 0, vr: 0, grow: 0 }, p)); }

  function confettiCannon(x, y, angle, count) {
    for (let i = 0; i < count; i++) {
      const a = angle + rand(-0.45, 0.45);
      const speed = rand(9, 22);
      add({ x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, g: 0.32, drag: 0.985, max: rand(3, 5.2), size: rand(6, 12), color: COLORS[(Math.random() * COLORS.length) | 0], shape: "rect", rot: rand(0, 6.28), vr: rand(-0.3, 0.3) });
    }
  }
  function firework(x, y) {
    const color = COLORS[(Math.random() * 6) | 0];
    for (let i = 0; i < 70; i++) {
      const a = (i / 70) * 6.283 + rand(-0.05, 0.05);
      const speed = rand(2, 7.5);
      add({ x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, g: 0.07, drag: 0.965, max: rand(0.9, 1.6), size: rand(1.6, 3), color, shape: "spark" });
    }
    sounds.pop();
  }
  function smoke(x, y, count) {
    for (let i = 0; i < count; i++) {
      add({ x: x + rand(-10, 10), y, vx: rand(-0.7, 0.7), vy: rand(-2.2, -0.8), drag: 0.99, max: rand(1.8, 3.2), size: rand(10, 20), grow: rand(0.35, 0.7), color: "170,178,195", shape: "puff" });
    }
  }
  function shards(x, y, count) {
    for (let i = 0; i < count; i++) {
      const a = rand(-Math.PI * 0.95, -Math.PI * 0.25);
      const speed = rand(3, 10);
      add({ x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, g: 0.4, drag: 0.985, max: rand(0.9, 1.6), size: rand(3, 7), color: ["#bae6fd", "#e0f2fe", "#cbd5e1"][i % 3], shape: "rect", rot: rand(0, 6.28), vr: rand(-0.5, 0.5) });
    }
  }
  function sparks(x, y, count) {
    for (let i = 0; i < count; i++) {
      const a = rand(-Math.PI, 0);
      const speed = rand(3, 9);
      add({ x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, g: 0.3, drag: 0.98, max: rand(0.5, 1.1), size: rand(1.5, 2.6), color: "#fdba74", shape: "spark" });
    }
  }

  function draw(now) {
    const dt = Math.min((now - last) / 16.67, 3);
    last = now;
    g.clearRect(0, 0, innerWidth, innerHeight);
    particles = particles.filter((p) => p.life < p.max);
    for (const p of particles) {
      p.life += dt / 60;
      p.vx *= Math.pow(p.drag, dt);
      p.vy = p.vy * Math.pow(p.drag, dt) + p.g * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.rot += p.vr * dt;
      p.size += p.grow * dt;
      const fade = Math.max(0, 1 - p.life / p.max);
      if (p.shape === "rect") {
        g.save();
        g.translate(p.x, p.y);
        g.rotate(p.rot);
        g.scale(1, Math.cos(p.life * 9 + p.rot)); // flutter
        g.globalAlpha = Math.min(1, fade * 2);
        g.fillStyle = p.color;
        g.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
        g.restore();
      } else if (p.shape === "puff") {
        g.globalAlpha = fade * 0.35;
        g.fillStyle = `rgb(${p.color})`;
        g.beginPath();
        g.arc(p.x, p.y, p.size, 0, 6.283);
        g.fill();
      } else {
        g.globalAlpha = fade;
        g.fillStyle = p.color;
        g.shadowColor = p.color;
        g.shadowBlur = 8;
        g.beginPath();
        g.arc(p.x, p.y, p.size * (0.4 + fade * 0.6), 0, 6.283);
        g.fill();
        g.shadowBlur = 0;
      }
    }
    g.globalAlpha = 1;
    frame = particles.length || root.dataset.live ? requestAnimationFrame(draw) : 0;
  }
  function run() {
    if (!frame) { last = performance.now(); frame = requestAnimationFrame(draw); }
  }

  // ---------- Markup ----------
  const carSvg = `
    <svg class="rv-car" viewBox="0 0 220 80" aria-hidden="true">
      <path class="rv-car__body" d="M10 56 Q12 42 32 38 L58 36 Q74 14 100 14 L140 14 Q160 16 172 36 L200 42 Q212 46 210 58 L208 62 L12 62 Z" />
      <path class="rv-car__glass" d="M70 36 Q82 20 100 20 L124 20 L124 36 Z M130 20 L142 20 Q154 24 160 36 L130 36 Z" />
      <rect class="rv-car__light" x="198" y="46" width="12" height="7" rx="3" />
      <rect class="rv-car__brake" x="9" y="44" width="9" height="8" rx="2" />
      <path class="rv-car__crack" d="M150 22 l-6 6 l5 3 l-7 5 M146 28 l7 4 M136 20 l4 9" />
      <path class="rv-car__dent" d="M176 38 L186 30 L190 41 L199 35 L206 47" />
      <g class="rv-car__wheel" style="--cx:56px"><circle cx="56" cy="62" r="15" /><path d="M56 49v26M43 62h26M47 53l18 18M65 53L47 71" /></g>
      <g class="rv-car__wheel" style="--cx:160px"><circle cx="160" cy="62" r="15" /><path d="M160 49v26M147 62h26M151 53l18 18M169 53l-18 18" /></g>
    </svg>`;

  function build() {
    const pct = d.percent;
    root.innerHTML = `
      <canvas class="rv-canvas" aria-hidden="true"></canvas>
      <div class="rv-flash"></div>
      <div class="rv-top">
        <button type="button" class="rv-chip" data-mute aria-label="${esc(muted ? t.unmute : t.mute)}"><i class="ti ${muted ? "ti-volume-off" : "ti-volume"}"></i></button>
        <button type="button" class="rv-chip rv-chip--text" data-skip>${esc(t.skip)} <i class="ti ti-player-skip-forward"></i></button>
      </div>

      <section class="rv-stage rv-tally">
        <p class="rv-counting">${esc(t.counting)}</p>
        <div class="rv-gauge">
          <svg viewBox="0 0 200 110" aria-hidden="true">
            <path class="rv-gauge__track" d="M15 100 A85 85 0 0 1 185 100" />
            <path class="rv-gauge__fill" d="M15 100 A85 85 0 0 1 185 100" pathLength="100" />
            <g class="rv-gauge__needle"><line x1="100" y1="100" x2="30" y2="100" /><circle cx="100" cy="100" r="7" /></g>
          </svg>
          <div class="rv-gauge__num"><b data-pct>0</b>%</div>
        </div>
        <div class="rv-counter"><span class="rv-ok"><i class="ti ti-check"></i><b data-ok>0</b></span><span class="rv-bad"><i class="ti ti-x"></i><b data-bad>0</b></span></div>
        <div class="rv-cells">${d.cells.map((c, i) => `<i data-s="${c}" style="--i:${i}"></i>`).join("")}</div>
      </section>

      <section class="rv-stage rv-pass" hidden>
        <div class="rv-card" data-card>
          <div class="rv-card__in">
            <div class="rv-card__top"><img src="${document.querySelector(".result-card__brand img")?.src || ""}" alt="AvtoIbrat"><span>${esc(t.cert)}</span></div>
            <div class="rv-card__mid">
              <div class="rv-chipic"></div>
              <div class="rv-card__name">${esc(d.name)}</div>
            </div>
            <div class="rv-card__bottom">
              <div class="rv-ring" style="--p:${pct}"><b>${pct}%</b></div>
              <div class="rv-card__facts"><b>${d.correct}</b> ${esc(t.of)} ${d.total} ${esc(t.correct)}<br><small>${d.wrong} ${esc(t.wrong)} · ${d.time}</small></div>
            </div>
            <div class="rv-stamp">${esc(t.pass_word)}</div>
            <div class="rv-sheen"></div>
          </div>
        </div>
        <h2 class="rv-title" data-type>${fill(t.pass_title)}</h2>
        <p class="rv-sub">${esc(t.pass_sub)}</p>
        <div class="rv-actions"><button type="button" class="rv-btn rv-btn--go" data-close autofocus>${esc(t.see)}</button></div>
      </section>

      <section class="rv-stage rv-fail" hidden>
        <svg class="rv-cracks" viewBox="0 0 400 300" preserveAspectRatio="none" aria-hidden="true">
          <path d="M200 150 L168 112 L150 60 L128 0" /><path d="M200 150 L238 118 L262 66 L300 0" />
          <path d="M200 150 L150 178 L96 176 L40 214 L0 220" /><path d="M200 150 L232 196 L214 252 L240 300" />
          <path d="M168 112 L120 118 L84 96" /><path d="M238 118 L290 126 L336 110" />
        </svg>
        <div class="rv-verdict glitch" data-text="${esc(t.fail_word)}">${esc(t.fail_word)}</div>
        <div class="rv-hope">
          <h2 class="rv-title">${fill(t.fail_title)}</h2>
          <p class="rv-sub">${esc(t.fail_sub)}</p>
          <div class="rv-compare">
            <div><small>${esc(t.allowed)}</small><b>${d.allowed}</b></div>
            <div class="is-bad"><small>${esc(t.made)}</small><b>${d.wrong}</b></div>
            <div><small>${esc(t.correct)}</small><b>${d.correct}/${d.total}</b></div>
          </div>
          <p class="rv-hint"><i class="ti ti-bulb"></i> ${esc(t.hope)}</p>
          <div class="rv-actions">
            <a class="rv-btn rv-btn--ghost" href="#" data-close>${esc(t.see)}</a>
            <a class="rv-btn rv-btn--go" href="${esc(d.restart)}"><i class="ti ti-refresh"></i> ${esc(t.retry)}</a>
          </div>
        </div>
      </section>

      <div class="rv-road"><div class="rv-road__line"></div><i class="rv-skid rv-skid--rear"></i><i class="rv-skid rv-skid--front"></i><div class="rv-barrier"></div>${carSvg}</div>`;

    canvas = root.querySelector(".rv-canvas");
    g = canvas.getContext("2d");
    sizeCanvas();
  }

  // ---------- Story ----------
  let token = 0;
  async function play() {
    const my = ++token;
    const alive = () => token === my;
    root.hidden = false;
    root.className = "rv is-live";
    root.dataset.live = "1";
    document.body.style.overflow = "hidden";
    build();
    run();
    if (!reduced) ctx();

    const q = (selector) => root.querySelector(selector);
    const needle = q(".rv-gauge__needle");
    const fillPath = q(".rv-gauge__fill");
    const setGauge = (percent) => {
      needle.style.transform = `rotate(${(percent / 100) * 180}deg)`;
      fillPath.style.strokeDashoffset = String(100 - percent);
    };
    setGauge(0);
    q(".rv-road").classList.add("is-driving");

    // 1) Tally: every question lights up in turn, the needle climbs with the score.
    const cells = Array.from(q(".rv-cells").children);
    const gap = Math.max(28, Math.min(95, 2400 / cells.length));
    let ok = 0;
    let bad = 0;
    for (let i = 0; i < cells.length; i++) {
      if (!alive()) return;
      const status = cells[i].dataset.s;
      cells[i].classList.add("on");
      if (status === "correct") ok++;
      else if (status === "wrong") bad++;
      q("[data-ok]").textContent = ok;
      q("[data-bad]").textContent = bad;
      const live = Math.round((ok / d.total) * 100);
      q("[data-pct]").textContent = live;
      setGauge(live + rand(-3, 3) * (status === "empty" ? 0 : 1));
      sounds.tick(status === "correct", i);
      if (status === "wrong") root.classList.add("rv-jolt"), setTimeout(() => root.classList.remove("rv-jolt"), 120);
      await wait(gap);
    }
    if (!alive()) return;
    setGauge(d.percent);
    q("[data-pct]").textContent = d.percent;
    q(".rv-counting").textContent = "…";
    root.classList.add("is-tense");
    sounds.heartbeat();
    await wait(900);
    sounds.heartbeat();
    await wait(1000);
    if (!alive()) return;

    // 2) Verdict
    root.classList.remove("is-tense");
    q(".rv-tally").classList.add("is-out");
    await wait(350);
    if (!alive()) return;
    q(".rv-tally").hidden = true;
    const verdict = () => {
      q(".rv-flash").classList.add("go");
      root.classList.add(d.passed ? "is-pass" : "is-fail", "rv-shake");
      setTimeout(() => root.classList.remove("rv-shake"), 700);
    };

    if (d.passed) {
      verdict();
      sounds.fanfare();
      q(".rv-pass").hidden = false;
      typeTitle(q("[data-type]"));
      confettiCannon(0, innerHeight, -1.05, 150);
      confettiCannon(innerWidth, innerHeight, -2.1, 150);
      for (let i = 0; i < 7; i++) setTimeout(() => alive() && firework(rand(innerWidth * 0.15, innerWidth * 0.85), rand(innerHeight * 0.12, innerHeight * 0.45)), 500 + i * 520);
      for (let i = 0; i < 4; i++) setTimeout(() => alive() && confettiCannon(rand(0, innerWidth), -20, 1.57, 40), 1200 + i * 900);
      run();
      tiltCard();
    } else {
      // Brakes: the barrier rushes in, wheels lock, skid marks, screech… then the impact.
      const road = q(".rv-road");
      road.classList.add("is-scene"); // the road grows into a close-up first
      await wait(550);
      if (!alive()) return;
      road.classList.add("is-braking");
      sounds.screech();
      await wait(900);
      if (!alive()) return;
      road.classList.remove("is-driving", "is-braking");
      road.classList.add("is-crashed");
      verdict();
      sounds.crash();
      setTimeout(() => alive() && sounds.fail(), 650);
      const carBox = q(".rv-car").getBoundingClientRect();
      const hit = { x: carBox.right - carBox.width * 0.06, y: carBox.top + carBox.height * 0.5 };
      sparks(hit.x, hit.y, 70);
      shards(hit.x - carBox.width * 0.25, carBox.top + carBox.height * 0.3, 36);
      smoke(hit.x, hit.y, 10);
      q(".rv-fail").hidden = false;
      const puff = setInterval(() => alive() && !root.classList.contains("is-hope") && (smoke(hit.x - carBox.width * 0.12, carBox.top + 6, 3), run()), 110);
      run();
      await wait(3000);
      clearInterval(puff);
      if (!alive()) return;
      root.classList.add("is-hope");
      road.classList.remove("is-crashed");
      road.classList.add("is-driving", "is-slow", "is-leaving");
      sounds.restart();
    }
  }

  function typeTitle(node) {
    const text = node.textContent;
    node.textContent = "";
    Array.from(text).forEach((char, i) => {
      const span = el("span", "rv-letter", char === " " ? "&nbsp;" : esc(char));
      span.style.animationDelay = `${0.35 + i * 0.035}s`;
      node.appendChild(span);
    });
  }

  function tiltCard() {
    const card = root.querySelector("[data-card]");
    if (!card) return;
    root.addEventListener("pointermove", (event) => {
      const x = (event.clientX / innerWidth - 0.5) * 2;
      const y = (event.clientY / innerHeight - 0.5) * 2;
      card.style.setProperty("--rx", `${-y * 10}deg`);
      card.style.setProperty("--ry", `${x * 14}deg`);
      card.style.setProperty("--sx", `${50 + x * 40}%`);
    });
  }

  function close() {
    token++;
    cancelAnimationFrame(frame);
    frame = 0;
    delete root.dataset.live;
    root.classList.add("is-closing");
    setTimeout(() => {
      root.hidden = true;
      root.innerHTML = "";
      particles = [];
      document.body.style.overflow = "";
    }, 450);
    store.set(seenKey, "1");
    document.getElementById("rv-replay")?.focus();
  }

  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-close], [data-skip]")) {
      event.preventDefault();
      close();
    }
    const mute = event.target.closest("[data-mute]");
    if (mute) {
      muted = !muted;
      store.set(muteKey, muted ? "1" : "0");
      mute.innerHTML = `<i class="ti ${muted ? "ti-volume-off" : "ti-volume"}"></i>`;
      mute.setAttribute("aria-label", muted ? t.unmute : t.mute);
    }
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !root.hidden) close(); });
  window.addEventListener("resize", () => { if (canvas) sizeCanvas(); });
  document.getElementById("rv-replay")?.addEventListener("click", play);

  if (!reduced && store.get(seenKey) !== "1") play();
})();
