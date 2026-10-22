(function () {
  "use strict";

  // Imtihonga yo‘l: draws each season as a winding road with one stop per bilet and drives the car
  // to the student's next stop. Progress made since the last visit (remembered per device) is
  // replayed: the car moves on, new stars light up, a finished season gets its ceremony.
  const root = document.getElementById("jr");
  const dataNode = document.getElementById("jr-data");
  if (!root || !dataNode) return;

  const D = JSON.parse(dataNode.textContent);
  const T = D.t;
  const NS = "http://www.w3.org/2000/svg";
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const scene = root.querySelector(".jr-scene");
  const mapBox = scene.querySelector(".jr-map");
  const lockBox = scene.querySelector(".jr-lock");
  const finalBox = scene.querySelector(".jr-final");
  const pop = scene.querySelector(".jr-pop");
  const toast = scene.querySelector(".jr-toast");
  const topo = scene.querySelector(".jr-topo");
  const canvas = scene.querySelector(".jr-particles");
  const tabs = Array.from(root.querySelectorAll(".jr-tab"));
  const hud = {
    index: scene.querySelector(".jr-hud__index"),
    title: scene.querySelector(".jr-hud h2"),
    motto: scene.querySelector(".jr-hud p"),
    cleared: scene.querySelector(".jr-hud__cleared"),
    stars: scene.querySelector(".jr-hud__stars"),
  };

  const seasons = D.seasons;
  const byKey = Object.fromEntries(seasons.map((s) => [s.key, s]));
  const ORDER = seasons.map((s) => s.key).concat("final");
  const alive = () => root.isConnected;

  // ---------- Small helpers ----------
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, reduced ? 0 : ms));
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const svg = (tag, attrs = {}, parent) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (parent) parent.appendChild(node);
    return node;
  };
  const esc = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const store = {
    get(key) { try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ } },
  };
  function seeded(seed) {
    return () => {
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function tween(duration, onFrame) {
    return new Promise((resolve) => {
      if (reduced || duration <= 0) { onFrame(1); resolve(); return; }
      const start = performance.now();
      const frame = (now) => {
        if (!alive()) return resolve();
        const t = Math.min(1, (now - start) / duration);
        onFrame(t);
        if (t < 1) requestAnimationFrame(frame); else resolve();
      };
      requestAnimationFrame(frame);
    });
  }
  function countTo(el, from, to, duration = 900) {
    if (!el) return;
    tween(duration, (t) => { el.textContent = Math.round(from + (to - from) * easeOut(t)); });
  }

  // ---------- What changed since the last visit ----------
  const memoKey = `ai.journey.${D.user}`;
  const before = store.get(memoKey);
  const starsNow = {};
  seasons.forEach((s) => s.stages.forEach((st) => { starsNow[st.id] = st.stars; }));
  const starsBefore = (id) => (before && before.c ? before.c[id] || 0 : starsNow[id]);
  const fresh = new Set(Object.keys(starsNow).map(Number).filter((id) => starsNow[id] > starsBefore(id)));
  const seasonsJustDone = seasons.filter((s) => s.done && before && !(before.d || []).includes(s.key)).map((s) => s.key);
  const certifiedJustNow = D.certified && before && !before.cert;
  store.set(memoKey, {
    c: starsNow,
    d: seasons.filter((s) => s.done).map((s) => s.key),
    cert: D.certified,
    r: D.readiness,
  });

  // ---------- Road geometry ----------
  // A serpentine: rows of stops, alternating direction, joined by U-turns, with a lead-in from the
  // start and a lead-out to the finish flag. Every curve continues the tangent of the one before.
  function geometry(count) {
    const narrow = mapBox.clientWidth < 640;
    const cols = narrow ? 3 : 5;
    const rows = Math.max(1, Math.ceil(count / cols));
    const W = narrow ? 360 : 1000;
    const gap = narrow ? 112 : 180;
    const rowH = narrow ? 132 : 150;
    const top = narrow ? 56 : 66;
    const lead = narrow ? 46 : 104;
    const turn = narrow ? 64 : 112;
    const amp = narrow ? 9 : 15;
    const x0 = (W - gap * (cols - 1)) / 2;
    const H = top * 2 + rowH * (rows - 1) + 18;

    const points = Array.from({ length: count }, (_, i) => {
      const row = Math.floor(i / cols);
      const col = i % cols;
      const ltr = row % 2 === 0;
      return { x: x0 + (ltr ? col : cols - 1 - col) * gap, y: top + row * rowH, row, dir: ltr ? 1 : -1 };
    });

    const f = (n) => n.toFixed(1);
    const start = { x: x0 - lead, y: top };
    const segments = [`M${f(start.x)} ${f(start.y)}`];
    let lastC2 = { x: start.x - 1, y: start.y };
    const curve = (p, q, c2, length) => {
      const vx = p.x - lastC2.x;
      const vy = p.y - lastC2.y;
      const norm = Math.hypot(vx, vy) || 1;
      const c1 = { x: p.x + (vx / norm) * length, y: p.y + (vy / norm) * length };
      lastC2 = c2;
      return `C${f(c1.x)} ${f(c1.y)} ${f(c2.x)} ${f(c2.y)} ${f(q.x)} ${f(q.y)}`;
    };

    let from = start;
    points.forEach((p, i) => {
      const sway = i % 2 ? amp : -amp;
      if (i > 0 && p.row !== points[i - 1].row) {
        const dir = points[i - 1].dir;
        segments.push(curve(from, p, { x: p.x + dir * turn, y: p.y }, turn));
      } else {
        const third = Math.abs(p.x - from.x) / 3;
        segments.push(curve(from, p, { x: p.x - p.dir * third, y: p.y + sway }, third));
      }
      from = p;
    });
    const last = points[points.length - 1] || start;
    const end = { x: last.x + (last.dir || 1) * lead, y: last.y };
    segments.push(curve(last, end, { x: end.x - (last.dir || 1) * lead / 3, y: end.y }, lead / 3));

    return { narrow, W, H, points, start, end, segments, d: segments.join(" ") };
  }

  // ---------- Map rendering ----------
  let view = null; // the drawn season: { key, svg, geo, lengths, total, nodes, car, done, carAt, ... }

  function starPath(r) {
    let d = "";
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 5;
      const rr = i % 2 ? r * 0.45 : r;
      d += `${i ? "L" : "M"}${(Math.cos(a) * rr).toFixed(2)} ${(Math.sin(a) * rr).toFixed(2)}`;
    }
    return d + "Z";
  }

  function buildDefs(root_, W) {
    const defs = svg("defs", {}, root_);
    const road = svg("linearGradient", { id: "jr-road-grad", gradientUnits: "userSpaceOnUse", x1: 0, y1: 0, x2: W, y2: 0 }, defs);
    svg("stop", { offset: 0, "stop-color": "var(--sc-accent-2)" }, road);
    svg("stop", { offset: 1, "stop-color": "var(--sc-accent)" }, road);
    const paint = svg("linearGradient", { id: "jr-car-paint", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    svg("stop", { offset: 0, "stop-color": "#f8fafc" }, paint);
    svg("stop", { offset: 0.55, "stop-color": "#cbd5e1" }, paint);
    svg("stop", { offset: 1, "stop-color": "#94a3b8" }, paint);
    const beam = svg("radialGradient", { id: "jr-beam", cx: 0, cy: 0.5, r: 1 }, defs);
    svg("stop", { offset: 0, "stop-color": "#fff8e1", "stop-opacity": 0.7 }, beam);
    svg("stop", { offset: 1, "stop-color": "#fff8e1", "stop-opacity": 0 }, beam);
    const mask = svg("mask", { id: "jr-road-mask", maskUnits: "userSpaceOnUse" }, defs);
    return { mask };
  }

  function buildCar(parent) {
    const car = svg("g", { class: "jr-car" }, parent);
    svg("path", { class: "jr-car__beam", d: "M15 -6 L78 -30 Q90 0 78 30 L15 6 Z" }, car);
    svg("ellipse", { class: "jr-car__shadow", cx: 1, cy: 3, rx: 19, ry: 11 }, car);
    svg("rect", { class: "jr-car__body", x: -17, y: -10, width: 34, height: 20, rx: 7 }, car);
    svg("rect", { class: "jr-car__glass", x: 2, y: -8, width: 8, height: 16, rx: 2.5 }, car);
    svg("rect", { class: "jr-car__glass", x: -12, y: -7.5, width: 5, height: 15, rx: 2 }, car);
    svg("rect", { class: "jr-car__shine", x: -6, y: -7, width: 7, height: 14, rx: 2 }, car);
    svg("rect", { class: "jr-car__light", x: 14, y: -8, width: 3, height: 4, rx: 1.2 }, car);
    svg("rect", { class: "jr-car__light", x: 14, y: 4, width: 3, height: 4, rx: 1.2 }, car);
    svg("rect", { class: "jr-car__tail", x: -17.5, y: -8, width: 2.4, height: 4, rx: 1 }, car);
    svg("rect", { class: "jr-car__tail", x: -17.5, y: 4, width: 2.4, height: 4, rx: 1 }, car);
    return car;
  }

  // The cloth flies back over the road, so the flag never pokes out of the scene's edge.
  function buildFlag(parent, at, narrow, dir) {
    const g = svg("g", { class: "jr-finish-flag", transform: `translate(${at.x} ${at.y - (narrow ? 30 : 34)})` }, parent);
    svg("line", { x1: 0, y1: 0, x2: 0, y2: 26 }, g);
    const x0 = dir > 0 ? -20 : 0;
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 4; c++) svg("rect", { class: (r + c) % 2 ? "b" : "a", x: x0 + c * 5, y: r * 5, width: 5, height: 5 }, g);
    }
    const label = svg("text", { x: 0, y: -8 }, g);
    label.textContent = T.finish.toUpperCase();
  }

  function nodeState(season, stage, shownStars) {
    if (!season.unlocked) return "is-locked";
    if (shownStars > 0) return "is-cleared";
    return stage.id === season.current ? "is-current" : "";
  }

  function paintNode(node, stars) {
    node.stars.forEach((path, i) => path.classList.toggle("is-on", i < stars));
  }

  function render(key, { replay = false } = {}) {
    mapBox.textContent = "";
    view = null;
    const season = byKey[key];
    if (!season || !season.stages.length) return;

    const geo = geometry(season.stages.length);
    const s = svg("svg", { viewBox: `0 0 ${geo.W} ${geo.H}`, role: "group", "aria-label": `${season.title} — ${season.stages.length}` });
    mapBox.appendChild(s);
    const { mask } = buildDefs(s, geo.W);

    // Distance along the road to every stop.
    const probe = svg("path", { d: geo.d, fill: "none" }, s);
    const total = probe.getTotalLength();
    const lengths = geo.points.map((_, i) => {
      probe.setAttribute("d", geo.segments.slice(0, i + 2).join(" "));
      return probe.getTotalLength();
    });
    probe.remove();

    const maskPath = svg("path", { d: geo.d, fill: "none", stroke: "#fff", "stroke-width": 70, "stroke-linecap": "round", "stroke-dasharray": `${total} ${total}`, "stroke-dashoffset": 0 }, mask);
    const roadGroup = svg("g", { mask: "url(#jr-road-mask)" }, s);
    svg("path", { class: "jr-road-shoulder", d: geo.d }, roadGroup);
    svg("path", { class: "jr-road", d: geo.d }, roadGroup);
    svg("path", { class: "jr-road-lane", d: geo.d }, roadGroup);
    const done = svg("path", { class: "jr-road-done", d: geo.d, "stroke-dasharray": `${total} ${total}`, "stroke-dashoffset": total }, s);
    svg("circle", { class: "jr-road-start", cx: geo.start.x, cy: geo.start.y, r: 5 }, roadGroup);
    buildFlag(roadGroup, geo.end, geo.narrow, geo.points.length ? geo.points[geo.points.length - 1].dir : 1);

    const R = geo.narrow ? 19 : 22;
    const star = starPath(geo.narrow ? 4.4 : 5);
    const nodes = season.stages.map((stage, i) => {
      const p = geo.points[i];
      const shown = replay && fresh.has(stage.id) ? starsBefore(stage.id) : stage.stars;
      const g = svg("g", {
        class: `jr-node ${nodeState(season, stage, shown)}`.trim(), transform: `translate(${p.x} ${p.y})`,
        tabindex: season.unlocked ? 0 : -1, role: "button", "data-id": stage.id,
        "aria-label": `${T.bilet} ${stage.n}${stage.cleared ? ` — ${T.cleared}, ${stage.stars} ${T.stars}` : ""}`,
      }, s);
      const body = svg("g", { class: "jr-node__body" }, g);
      svg("circle", { class: "jr-node__halo", r: R }, body);
      svg("circle", { class: "jr-node__ring", r: R }, body);
      svg("circle", { class: "jr-node__core", r: R - 7 }, body);
      svg("text", { class: "jr-node__num", y: 0.5 }, body).textContent = stage.n;
      const row = svg("g", { class: "jr-node__stars", transform: `translate(0 ${R + 12})` }, g);
      const stars = [-12, 0, 12].map((x) => svg("path", { d: star, transform: `translate(${x} 0)` }, row));
      const node = { stage, g, body, stars, at: lengths[i], point: p, shown };
      paintNode(node, shown);
      return node;
    });

    const car = season.unlocked ? buildCar(s) : null;
    const gap = geo.narrow ? 32 : 40;
    view = { key, season, svg: s, geo, lengths, total, nodes, car, done, mask: maskPath, R, carAt: 0, gap };
    return view;
  }

  // Where the car parks for a given state: just before the next unfinished stop, or at the finish.
  function parking(season, starsOf) {
    if (!view) return 0;
    const next = view.nodes.find((n) => starsOf(n.stage.id) === 0);
    return next ? Math.max(0, next.at - view.gap) : view.total - 8;
  }

  function placeCar(at) {
    if (!view || !view.car) return;
    const probe = view.svg.querySelector(".jr-road");
    const len = Math.max(0.5, Math.min(view.total - 0.5, at));
    const p = probe.getPointAtLength(len);
    const a = probe.getPointAtLength(Math.max(0, len - 1));
    const b = probe.getPointAtLength(Math.min(view.total, len + 1));
    const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
    view.car.setAttribute("transform", `translate(${p.x.toFixed(2)} ${p.y.toFixed(2)}) rotate(${angle.toFixed(2)})`);
    view.done.setAttribute("stroke-dashoffset", (view.total - at).toFixed(2));
    view.carAt = at;
    return p;
  }

  function youAreHere() {
    if (!view) return;
    view.svg.querySelectorAll(".jr-youare").forEach((n) => n.remove());
    const current = view.nodes.find((n) => n.stage.id === view.season.current);
    if (!current) return;
    const w = T.you.length * 6.4 + 20;
    const g = svg("g", { class: "jr-youare", transform: `translate(${current.point.x} ${current.point.y - view.R - 22})` }, view.svg);
    svg("rect", { x: -w / 2, y: -11, width: w, height: 22, rx: 11 }, g);
    svg("path", { d: "M-5 10 L0 16 L5 10 Z", fill: "#fff" }, g);
    svg("text", { y: 0.5 }, g).textContent = T.you;
    if (!reduced) g.animate([{ opacity: 0, transform: `translate(${current.point.x}px, ${current.point.y - view.R - 14}px)` }, { opacity: 1, transform: `translate(${current.point.x}px, ${current.point.y - view.R - 22}px)` }], { duration: 420, easing: "cubic-bezier(.22,1,.36,1)" });
  }

  // A soft trail of sparks behind the moving car.
  function spark(p) {
    if (reduced || !view) return;
    const dot = svg("circle", { class: "jr-spark", cx: p.x + (Math.random() - 0.5) * 8, cy: p.y + (Math.random() - 0.5) * 8, r: 1.4 + Math.random() * 1.6 }, view.svg);
    view.svg.insertBefore(dot, view.car);
    dot.style.transformBox = "fill-box";
    dot.style.transformOrigin = "center";
    dot.animate([{ opacity: 0.9, transform: "scale(1)" }, { opacity: 0, transform: "scale(0.2)" }], { duration: 700, easing: "ease-out" }).onfinish = () => dot.remove();
  }

  function clearNode(node) {
    node.g.classList.remove("is-current");
    node.g.classList.add("is-cleared", "is-burst");
    node.stars.forEach((path, i) => {
      if (i >= node.stage.stars || i < node.shown) return;
      setTimeout(() => path.classList.add("is-on"), reduced ? 0 : 160 + (i - node.shown) * 140);
    });
    node.shown = node.stage.stars;
    const rect = node.g.getBoundingClientRect();
    const box = scene.getBoundingClientRect();
    particles.burst(rect.left + rect.width / 2 - box.left, rect.top + rect.height / 2 - box.top, 26);
    setTimeout(() => node.g.classList.remove("is-burst"), 800);
  }

  async function drive(from, to) {
    if (!view || !view.car) return;
    const distance = Math.abs(to - from);
    const duration = Math.min(2600, 500 + distance * 1.6);
    const pending = view.nodes.filter((n) => n.shown < n.stage.stars);
    let lastSpark = 0;
    await tween(duration, (t) => {
      const at = from + (to - from) * easeInOut(t);
      const p = placeCar(at);
      const now = performance.now();
      if (p && now - lastSpark > 45 && t < 0.97) { spark(p); lastSpark = now; }
      pending.forEach((n) => { if (n.shown < n.stage.stars && at >= n.at - 4) clearNode(n); });
    });
    // Stages cleared out of order (further than the car went) light up when it arrives.
    pending.forEach((n) => { if (n.shown < n.stage.stars) clearNode(n); });
    view.nodes.forEach((n) => {
      n.g.classList.toggle("is-current", n.stage.id === view.season.current);
    });
  }

  // The road draws itself, stops pop in as the road reaches them, then the car rolls out.
  async function intro({ fromAt = 0, replay = false } = {}) {
    if (!view) return;
    const { total, mask, nodes } = view;
    const drawMs = reduced ? 0 : 900;
    if (!reduced) {
      mask.animate([{ strokeDashoffset: total }, { strokeDashoffset: 0 }], { duration: drawMs, easing: "cubic-bezier(.65,0,.35,1)" });
      nodes.forEach((n) => {
        const delay = (n.at / total) * drawMs * 0.9;
        n.g.animate([{ opacity: 0, transform: `translate(${n.point.x}px, ${n.point.y + 10}px) scale(0.6)` }, { opacity: 1, transform: `translate(${n.point.x}px, ${n.point.y}px) scale(1)` }], { duration: 480, delay, easing: "cubic-bezier(.34,1.56,.64,1)", fill: "backwards" });
      });
      if (view.car) view.car.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, delay: drawMs * 0.4, fill: "backwards" });
    }
    if (!view.car) return;
    placeCar(fromAt);
    await wait(drawMs * 0.55);
    const target = parking(view.season, (id) => byKey[view.key].stages.find((s) => s.id === id).stars);
    await drive(fromAt, target);
    youAreHere();
    if (replay) announce();
  }

  function announce() {
    const gained = view.nodes.filter((n) => fresh.has(n.stage.id));
    if (!gained.length) return;
    const latest = gained[gained.length - 1].stage;
    const text = gained.length === 1
      ? `${T.bilet} ${latest.n} ${T.stage_done}`
      : `+${gained.length} · ${T.bilet} ${gained.map((n) => n.stage.n).join(", ")}`;
    showToast(`<i class="ti ti-check"></i><span>${esc(text)}</span><em>${"★".repeat(latest.stars)}</em>`);
  }

  let toastTimer = null;
  function showToast(html) {
    toast.innerHTML = html;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 4200);
  }

  // ---------- Stage card ----------
  function closePop() {
    pop.hidden = true;
    pop.textContent = "";
  }

  function openPop(node) {
    const { stage } = node;
    const season = view.season;
    const next = stage.id === season.current;
    const status = stage.cleared
      ? `<span class="jr-pop__status is-ok"><i class="ti ti-circle-check"></i>${esc(T.cleared)}</span>`
      : next ? `<span class="jr-pop__status is-next"><i class="ti ti-target"></i>${esc(T.next)}</span>`
        : `<span class="jr-pop__status"><i class="ti ti-circle-dashed"></i>${esc(T.open)}</span>`;
    const stars = [0, 1, 2].map((i) => `<span class="${i < stage.stars ? "is-on" : ""}">★</span>`).join("");
    const url = D.start_url.replace(/\/0\/(?=[^/]*$)/, `/${stage.id}/`);
    pop.innerHTML = `
      <div class="jr-pop__head"><b>${esc(T.bilet)} ${stage.n}</b>
        <button type="button" class="jr-pop__close" aria-label="${esc(T.close)}"><i class="ti ti-x"></i></button></div>
      ${status}
      <div class="jr-pop__stars" aria-label="${stage.stars} ${esc(T.stars)}">${stars}</div>
      <div class="jr-pop__grid">
        <div><small>${esc(T.best)}</small><b>${stage.best === null ? "—" : `${stage.best}%`}</b></div>
        <div><small>${esc(T.attempts)}</small><b>${stage.attempts}</b></div>
      </div>
      <p class="jr-pop__rule">${esc(stage.stars === 3 ? T.perfect : T.rule)}</p>
      <a class="jr-btn jr-btn--primary" href="${url}"><i class="ti ti-player-play"></i>${esc(stage.attempts ? T.again : T.start)}</a>`;
    pop.hidden = false;

    const box = scene.getBoundingClientRect();
    const r = node.body.getBoundingClientRect();
    const cx = r.left + r.width / 2 - box.left;
    const width = pop.offsetWidth;
    const height = pop.offsetHeight;
    const left = Math.max(12, Math.min(box.width - width - 12, cx - width / 2));
    const above = r.top - box.top - height - 14;
    const top = above > 12 ? above : r.bottom - box.top + 30;
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
    pop.style.setProperty("--ox", `${cx - left}px`);
    pop.style.setProperty("--oy", above > 12 ? "100%" : "0%");
    pop.querySelector(".jr-pop__close").addEventListener("click", closePop);
    pop.querySelector("a").focus({ preventScroll: true });
  }

  mapBox.addEventListener("click", (event) => {
    const g = event.target.closest(".jr-node");
    if (!g || !view || !view.season.unlocked) return;
    event.stopPropagation();
    const node = view.nodes.find((n) => String(n.stage.id) === g.dataset.id);
    if (node) openPop(node);
  });
  mapBox.addEventListener("keydown", (event) => {
    const g = event.target.closest(".jr-node");
    if (!g || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    g.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  scene.addEventListener("click", (event) => { if (!pop.hidden && !pop.contains(event.target)) closePop(); });
  const onKey = (event) => {
    if (!alive()) { document.removeEventListener("keydown", onKey); return; }
    if (event.key === "Escape") closePop();
  };
  document.addEventListener("keydown", onKey);

  // ---------- Contour lines behind the map ----------
  function drawTopo(key) {
    const w = scene.clientWidth;
    const h = scene.clientHeight;
    topo.setAttribute("viewBox", `0 0 ${w} ${h}`);
    topo.textContent = "";
    const rnd = seeded(ORDER.indexOf(key) * 7919 + 17);
    const scale = Math.max(0.6, w / 1100);
    for (let c = 0; c < 3; c++) {
      const cx = rnd() * w;
      const cy = rnd() * h;
      const phases = [rnd() * 6.28, rnd() * 6.28, rnd() * 6.28];
      for (let k = 1; k <= 9; k++) {
        const radius = (24 + k * 30) * scale;
        const pts = [];
        for (let i = 0; i < 40; i++) {
          const a = (i / 40) * Math.PI * 2;
          const wobble = 1 + 0.16 * Math.sin(3 * a + phases[0]) + 0.09 * Math.sin(5 * a + phases[1]) + (0.05 * k / 9) * Math.sin(2 * a + phases[2]);
          pts.push([cx + Math.cos(a) * radius * wobble * 1.25, cy + Math.sin(a) * radius * wobble]);
        }
        // Closed Catmull-Rom spline through the points.
        let d = `M${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
        for (let i = 0; i < pts.length; i++) {
          const p0 = pts[(i - 1 + pts.length) % pts.length];
          const p1 = pts[i];
          const p2 = pts[(i + 1) % pts.length];
          const p3 = pts[(i + 2) % pts.length];
          d += `C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)} ${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)} ${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
        }
        svg("path", { d }, topo);
      }
    }
  }

  // ---------- Season weather (canvas) ----------
  const particles = (() => {
    const ctx = canvas.getContext("2d");
    const kinds = {
      spring: { colors: ["#fbcfe8", "#f9a8d4", "#ecfccb", "#ffffff"], shape: "petal", fall: -0.12, drift: 0.25, size: [2, 4.2], alpha: [0.25, 0.6] },
      summer: { colors: ["#fde68a", "#fbbf24", "#fff7d6"], shape: "mote", fall: -0.2, drift: 0.08, size: [0.8, 2.2], alpha: [0.2, 0.7] },
      autumn: { colors: ["#fb923c", "#f97316", "#b45309", "#fcd34d"], shape: "leaf", fall: 0.45, drift: 0.35, size: [3, 5.5], alpha: [0.35, 0.75] },
      winter: { colors: ["#ffffff", "#e0f2fe", "#dbeafe"], shape: "snow", fall: 0.5, drift: 0.2, size: [0.8, 2.8], alpha: [0.35, 0.85] },
      final: { colors: ["#fde68a", "#e9c46a", "#ffffff"], shape: "mote", fall: -0.06, drift: 0.05, size: [0.8, 2], alpha: [0.2, 0.8] },
    };
    let kind = kinds.spring;
    let flakes = [];
    let bursts = [];
    let w = 0;
    let h = 0;
    let running = false;
    let visible = true;

    const rand = (a, b) => a + Math.random() * (b - a);
    function spawn(anywhere) {
      return {
        x: rand(0, w), y: anywhere ? rand(0, h) : (kind.fall > 0 ? -10 : h + 10),
        r: rand(kind.size[0], kind.size[1]), a: rand(kind.alpha[0], kind.alpha[1]),
        vy: kind.fall * rand(0.5, 1.4), vx: rand(-kind.drift, kind.drift),
        rot: rand(0, 6.28), spin: rand(-0.02, 0.02), phase: rand(0, 6.28),
        color: kind.colors[Math.floor(Math.random() * kind.colors.length)],
      };
    }
    function resize() {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      w = scene.clientWidth;
      h = scene.clientHeight;
      canvas.width = w * ratio;
      canvas.height = h * ratio;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      const count = Math.min(70, Math.round((w * h) / 15000));
      flakes = Array.from({ length: count }, () => spawn(true));
    }
    function drawFlake(p, t) {
      ctx.globalAlpha = p.a * (kind.shape === "mote" ? 0.6 + 0.4 * Math.sin(t / 700 + p.phase) : 1);
      ctx.fillStyle = p.color;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.beginPath();
      if (kind.shape === "leaf") ctx.ellipse(0, 0, p.r, p.r * 0.45, 0, 0, Math.PI * 2);
      else if (kind.shape === "petal") ctx.ellipse(0, 0, p.r, p.r * 0.6, 0, 0, Math.PI * 2);
      else ctx.arc(0, 0, p.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    function frame(t) {
      if (!alive()) { running = false; return; }
      if (!visible || document.hidden) { running = false; return; }
      ctx.clearRect(0, 0, w, h);
      flakes.forEach((p, i) => {
        p.x += p.vx + Math.sin(t / 1400 + p.phase) * kind.drift * 0.6;
        p.y += p.vy;
        p.rot += p.spin;
        if (p.y > h + 12 || p.y < -12 || p.x < -12 || p.x > w + 12) flakes[i] = spawn(false);
        drawFlake(p, t);
      });
      bursts = bursts.filter((b) => b.life > 0);
      bursts.forEach((b) => {
        b.x += b.vx; b.y += b.vy; b.vy += 0.08; b.vx *= 0.985; b.life -= 1;
        ctx.globalAlpha = Math.max(0, b.life / b.max);
        ctx.fillStyle = b.color;
        ctx.fillRect(b.x, b.y, b.size, b.size * 0.6);
      });
      ctx.globalAlpha = 1;
      requestAnimationFrame(frame);
    }
    function start() {
      if (running || reduced) return;
      running = true;
      requestAnimationFrame(frame);
    }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) start(); }).observe(scene);
    }
    document.addEventListener("visibilitychange", () => { if (!document.hidden && alive()) start(); });
    return {
      set(key) {
        kind = kinds[key] || kinds.spring;
        resize();
        if (reduced) { ctx.clearRect(0, 0, w, h); flakes.forEach((p) => drawFlake(p, 0)); }
        start();
      },
      resize,
      burst(x, y, count = 60) {
        if (reduced) return;
        const colors = [getComputedStyle(scene).getPropertyValue("--sc-accent").trim() || "#34d399", "#fde68a", "#ffffff"];
        for (let i = 0; i < count; i++) {
          const a = Math.random() * Math.PI * 2;
          const speed = rand(1.5, count > 40 ? 7 : 4);
          const life = Math.round(rand(40, 80));
          bursts.push({ x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed - 1.5, size: rand(2, 4.5), life, max: life, color: colors[i % colors.length] });
        }
        start();
      },
    };
  })();

  // ---------- Season switching ----------
  let currentKey = null;
  let switching = Promise.resolve();

  function updateHud(key) {
    const index = ORDER.indexOf(key);
    if (key === "final") {
      hud.index.textContent = `05 · ${T.finish}`;
      hud.title.textContent = T.final_title;
      hud.motto.textContent = T.final_motto;
      hud.cleared.textContent = `${D.cleared}/${seasons.reduce((n, s) => n + s.stages.length, 0)}`;
      hud.stars.textContent = `${seasons.reduce((n, s) => n + s.stars, 0)}/${seasons.reduce((n, s) => n + s.max_stars, 0)}`;
      return;
    }
    const s = byKey[key];
    hud.index.textContent = `${T.season_label} 0${index + 1} / 04`;
    hud.title.textContent = s.title;
    hud.motto.textContent = s.motto;
    hud.cleared.textContent = `${s.stages.filter((st) => st.cleared).length}/${s.stages.length}`;
    hud.stars.textContent = `${s.stars}/${s.max_stars}`;
  }

  function lockMessage(key) {
    const previous = seasons[ORDER.indexOf(key) - 1];
    if (key === "final") return "";
    const done = previous ? previous.stages.filter((st) => st.cleared).length : 0;
    return `${T.locked}: ${previous ? previous.title : ""} — ${done}/${previous ? previous.stages.length : 0}`;
  }

  function show(key, { replay = false, scroll = false } = {}) {
    switching = switching.then(async () => {
      if (!alive()) return;
      closePop();
      tabs.forEach((tab) => {
        const on = tab.dataset.season === key;
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
      });
      if (scroll) scene.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });
      const first = currentKey === null;
      if (!first) {
        scene.classList.add("is-switching");
        await wait(340);
      }
      currentKey = key;
      scene.dataset.season = key;
      updateHud(key);
      drawTopo(key);
      particles.set(key);

      const isFinal = key === "final";
      finalBox.hidden = !isFinal;
      mapBox.hidden = isFinal;
      const season = byKey[key];
      lockBox.hidden = isFinal || season.unlocked;
      if (!lockBox.hidden) lockBox.querySelector(".jr-lock__text").textContent = lockMessage(key);
      if (isFinal) {
        mapBox.textContent = "";
        view = null;
      } else {
        render(key, { replay });
      }
      scene.classList.remove("is-switching");

      if (!view) return;
      let fromAt = 0;
      if (replay && before) fromAt = parking(season, starsBefore);
      await intro({ fromAt, replay });
    });
    return switching;
  }

  // ---------- Ceremonies ----------
  function ceremony({ kicker, title, sub, stars, button, icon }) {
    return new Promise((resolve) => {
      if (!alive()) return resolve();
      const box = document.createElement("div");
      box.className = "jr-ceremony";
      box.setAttribute("role", "dialog");
      box.setAttribute("aria-label", title);
      box.innerHTML = `
        <div class="jr-medal" aria-hidden="true">
          <svg viewBox="0 0 132 132">
            <g class="jr-medal__rays">${Array.from({ length: 24 }, (_, i) => `<rect x="65" y="0" width="2" height="18" rx="1" fill="var(--sc-accent)" opacity="${i % 2 ? 0.25 : 0.55}" transform="rotate(${i * 15} 66 66)"/>`).join("")}</g>
            <circle cx="66" cy="66" r="42" fill="var(--sc-accent)"/>
            <circle cx="66" cy="66" r="35" fill="none" stroke="rgba(255,255,255,.55)" stroke-width="1.5" stroke-dasharray="3 4"/>
          </svg>
          <i class="ti ${icon}" style="position:absolute;inset:0;display:grid;place-items:center;font-size:40px;color:#0b1110"></i>
        </div>
        <p class="jr-ceremony__kicker">${esc(kicker)}</p>
        <h3>${esc(title)}</h3>
        ${stars ? `<span class="jr-ceremony__stars">★ ${esc(stars)}</span>` : ""}
        <p>${esc(sub)}</p>
        <button type="button" class="jr-btn jr-btn--light">${esc(button)}<i class="ti ti-arrow-right"></i></button>`;
      scene.appendChild(box);
      const box_ = scene.getBoundingClientRect();
      particles.burst(box_.width / 2, box_.height / 2 - 60, 120);
      const close = () => {
        clearTimeout(timer);
        box.classList.add("is-leaving");
        setTimeout(() => { box.remove(); resolve(); }, reduced ? 0 : 420);
      };
      const timer = setTimeout(close, 6500);
      box.querySelector("button").addEventListener("click", close, { once: true });
      box.querySelector("button").focus({ preventScroll: true });
    });
  }

  const SEASON_ICONS = { spring: "ti-plant-2", summer: "ti-sun", autumn: "ti-leaf", winter: "ti-snowflake" };

  async function playJustDone() {
    // Several seasons finished since the last visit: celebrate the latest one only.
    for (const key of seasonsJustDone.slice(-1)) {
      await show(key, { replay: true });
      await wait(500);
      const s = byKey[key];
      const next = seasons[ORDER.indexOf(key) + 1];
      await ceremony({
        kicker: `${T.season_label} 0${ORDER.indexOf(key) + 1}`,
        title: `${s.title} ${T.season_done}`,
        stars: `${s.stars}/${s.max_stars}`,
        sub: next ? `${T.season_next}: ${next.title}` : T.final_motto,
        button: T.continue,
        icon: SEASON_ICONS[key],
      });
    }
    if (certifiedJustNow) {
      await show("final");
      await ceremony({ kicker: T.finish, title: T.certified, sub: T.certified_sub, button: T.see_cert, icon: "ti-certificate" });
      return;
    }
    const next = D.active;
    await show(next, { replay: !seasonsJustDone.includes(next) });
  }

  // ---------- Hero: gauge, counters, meters ----------
  function hero() {
    const gauge = root.querySelector(".jr-gauge");
    const value = gauge.querySelector(".jr-gauge__value");
    const num = gauge.querySelector(".jr-gauge__num");
    const target = Number(gauge.dataset.value) || 0;
    const from = before && typeof before.r === "number" ? Math.min(before.r, target) : 0;
    value.style.transition = "none";
    value.style.strokeDasharray = `${from * 0.75} 100`;
    num.textContent = from;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      value.style.transition = "";
      value.style.strokeDasharray = `${target * 0.75} 100`;
      countTo(num, from, target, 1500);
      root.classList.add("is-live");
    }));
    root.querySelectorAll(".jr-facts [data-count]").forEach((el) => countTo(el, 0, Number(el.dataset.count) || 0, 1000));
  }

  // ---------- Wiring ----------
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => show(tab.dataset.season));
    tab.addEventListener("keydown", (event) => {
      const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      event.preventDefault();
      const next = tabs[(i + step + tabs.length) % tabs.length];
      next.focus();
      show(next.dataset.season);
    });
  });
  root.querySelectorAll("[data-jr-go]").forEach((button) => button.addEventListener("click", () => show(button.dataset.jrGo, { scroll: true })));
  root.querySelectorAll("[data-jr-print]").forEach((button) => button.addEventListener("click", () => window.print()));

  // Re-lay the road when the map changes between the wide and the narrow layout.
  if ("ResizeObserver" in window) {
    let wasNarrow = null;
    let timer = null;
    new ResizeObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (!alive() || !currentKey) return;
        const narrow = mapBox.clientWidth < 640;
        particles.resize();
        drawTopo(currentKey);
        if (wasNarrow !== null && narrow !== wasNarrow && view) {
          closePop();
          render(currentKey);
          if (view && view.car) { placeCar(parking(view.season, (id) => starsNow[id])); youAreHere(); }
        }
        wasNarrow = narrow;
      }, 150);
    }).observe(scene);
  }

  hero();
  playJustDone();
})();
