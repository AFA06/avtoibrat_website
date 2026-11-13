(function () {
  "use strict";

  // Imtihonga yo‘l: the whole journey is one mountain. Bahor is the foothills, Yoz and Kuz the middle
  // slopes, Qish the snow cap and the real exam the summit. A switchback road climbs it with one stop
  // per bilet; the student's car parks below the next unfinished stop. Progress since the last visit
  // (remembered per device) is replayed: the car labours up the road, slips on the steep turns, lights
  // the stops it passes and lifts the barrier of a finished season.
  const root = document.getElementById("jr");
  const dataNode = document.getElementById("jr-data");
  if (!root || !dataNode) return;

  const D = JSON.parse(dataNode.textContent);
  const T = D.t;
  const NS = "http://www.w3.org/2000/svg";
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const scene = root.querySelector(".jr-scene");
  const mapBox = scene.querySelector(".jr-map");
  const finalBox = scene.querySelector(".jr-final");
  const pop = scene.querySelector(".jr-pop");
  const toast = scene.querySelector(".jr-toast");
  const canvas = scene.querySelector(".jr-particles");
  const railBox = scene.querySelector(".jr-rail");
  const tabs = Array.from(root.querySelectorAll(".jr-tab"));
  const hud = {
    index: scene.querySelector(".jr-hud__index"),
    title: scene.querySelector(".jr-hud h2"),
    motto: scene.querySelector(".jr-hud p"),
    alt: scene.querySelector(".jr-hud__alt"),
    left: scene.querySelector(".jr-hud__left"),
    stars: scene.querySelector(".jr-hud__stars"),
  };

  const seasons = D.seasons;
  const byKey = Object.fromEntries(seasons.map((s) => [s.key, s]));
  const ORDER = seasons.map((s) => s.key).concat("final");
  const ZONE_COLOR = { spring: "#3fcf96", summer: "#f0b545", autumn: "#ef8a4e", winter: "#8ec5ff", final: "#e9c46a" };
  const alive = () => root.isConnected;

  // ---------- Small helpers ----------
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, reduced ? 0 : ms));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const f1 = (n) => n.toFixed(1);
  const svg = (tag, attrs = {}, parent) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (parent) parent.appendChild(node);
    return node;
  };
  const esc = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const meters = (n) => `${Math.round(n).toLocaleString("ru-RU")} ${T.m}`;
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
        if (onFrame(t) === false) return resolve();
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

  // Every bilet in road order, with its season.
  const stops = [];
  seasons.forEach((season, zone) => season.stages.forEach((stage) => stops.push({ stage, season, zone })));
  const allDone = seasons.length > 0 && seasons.every((s) => s.done);

  // ---------- The mountain ----------
  // World units: the mountain is 1800 wide; its height grows with the number of switchback rows.
  const W = 1800;
  const CX = 900;
  const PEAK_Y = 220;
  const ROW_H = 132;
  const ALT_BASE = 600;
  const ALT_TOP = 3600;

  function layout(count) {
    const rows = clamp(Math.round(count / 6), 4, 14);
    const baseY = PEAK_Y + 160 + rows * ROW_H;
    const H = baseY + 170;
    const span = baseY - PEAK_Y;
    const half = (y) => 760 * Math.pow(Math.max(0, (y - PEAK_Y) / span), 0.82);
    const rnd = seeded(4242);
    const rise = ROW_H * 0.22;

    const rowsInfo = Array.from({ length: rows }, (_, r) => {
      const y = baseY - 80 - r * ROW_H;
      const dir = r % 2 === 0 ? 1 : -1;
      const hw = half(y) * 0.8;
      return { y, dir, xa: CX - dir * hw, xb: CX + dir * hw, yEnd: y - rise };
    });

    // The road: a lead-in, then rows across the face joined by hairpins, then the last climb to the
    // summit. Every joint is horizontal, so the curve is smooth everywhere.
    const first = rowsInfo[0];
    const start = { x: first.xa - 150, y: first.y + 26 };
    const segs = [{ kind: "lead", d: `C${f1(start.x + 60)} ${f1(start.y)} ${f1(first.xa - 60)} ${f1(first.y)} ${f1(first.xa)} ${f1(first.y)}` }];
    rowsInfo.forEach((row, r) => {
      const k = Math.abs(row.xb - row.xa) / 6;
      const mid = { x: (row.xa + row.xb) / 2, y: row.y - rise / 2 + (rnd() - 0.5) * 18 };
      segs.push({ kind: "row", row: r, d: `C${f1(row.xa + row.dir * k)} ${f1(row.y)} ${f1(mid.x - row.dir * k)} ${f1(mid.y + rise / 6)} ${f1(mid.x)} ${f1(mid.y)}` });
      segs.push({ kind: "row", row: r, d: `C${f1(mid.x + row.dir * k)} ${f1(mid.y - rise / 6)} ${f1(row.xb - row.dir * k)} ${f1(row.yEnd)} ${f1(row.xb)} ${f1(row.yEnd)}` });
      const next = rowsInfo[r + 1];
      if (next) {
        const ext = (row.yEnd - next.y) * 0.62;
        segs.push({ kind: "turn", row: r, d: `C${f1(row.xb + row.dir * ext)} ${f1(row.yEnd)} ${f1(next.xa + row.dir * ext)} ${f1(next.y)} ${f1(next.xa)} ${f1(next.y)}` });
      }
    });
    const last = rowsInfo[rows - 1];
    const summit = { x: CX, y: PEAK_Y + 52 };
    const ext = (last.yEnd - summit.y) * 0.55;
    segs.push({ kind: "summit", d: `C${f1(last.xb + last.dir * ext)} ${f1(last.yEnd)} ${f1(summit.x + last.dir * 90)} ${f1(summit.y)} ${f1(summit.x)} ${f1(summit.y)}` });

    const d = `M${f1(start.x)} ${f1(start.y)} ${segs.map((s) => s.d).join(" ")}`;
    return { rows, baseY, H, span, half, rowsInfo, start, summit, segs, d };
  }

  // Arc length at the end of every segment, measured on a scratch path.
  function measure(geo, host) {
    const probe = svg("path", { fill: "none" }, host);
    let d = `M${f1(geo.start.x)} ${f1(geo.start.y)}`;
    const ends = geo.segs.map((s) => {
      d += ` ${s.d}`;
      probe.setAttribute("d", d);
      return probe.getTotalLength();
    });
    probe.remove();
    return ends;
  }

  // Stops go on the straight rows only (never in a hairpin), shared out by row length.
  function placeStops(geo, ends, count) {
    const MARGIN = 38;
    const rows = [];
    geo.segs.forEach((s, i) => {
      if (s.kind !== "row") return;
      const a = i ? ends[i - 1] : 0;
      const row = rows[s.row] || (rows[s.row] = { a, b: ends[i] });
      row.b = ends[i];
    });
    const usable = rows.map((r) => Math.max(0, r.b - r.a - 2 * MARGIN));
    const sum = usable.reduce((n, u) => n + u, 0) || 1;
    const exact = usable.map((u) => (u / sum) * count);
    const counts = exact.map(Math.floor);
    let left = count - counts.reduce((n, c) => n + c, 0);
    exact.map((e, i) => [e - Math.floor(e), i]).sort((p, q) => q[0] - p[0]).forEach(([, i]) => { if (left > 0) { counts[i] += 1; left -= 1; } });
    const at = [];
    rows.forEach((r, i) => {
      for (let k = 0; k < counts[i]; k++) at.push(r.a + MARGIN + ((k + 0.5) * usable[i]) / counts[i]);
    });
    return at;
  }

  // ---------- Scene state ----------
  let M = null; // the drawn mountain: { svg, geo, total, road, nodes, car, camps, zones, ... }

  function starPath(r) {
    let d = "";
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 5;
      const rr = i % 2 ? r * 0.45 : r;
      d += `${i ? "L" : "M"}${(Math.cos(a) * rr).toFixed(2)} ${(Math.sin(a) * rr).toFixed(2)}`;
    }
    return d + "Z";
  }

  function ridgeLine(rnd, x0, x1, base, step, height) {
    // A far mountain range: a jagged skyline from x0 to x1 above `base`.
    const pts = [];
    const p = [rnd() * 6.28, rnd() * 6.28, rnd() * 6.28];
    for (let x = x0; x <= x1; x += step) {
      const h = height * (0.45 + 0.3 * Math.sin(x / 410 + p[0]) + 0.17 * Math.sin(x / 157 + p[1]) + 0.08 * Math.sin(x / 61 + p[2])) + (rnd() - 0.5) * height * 0.08;
      pts.push(`${f1(x)} ${f1(base - h)}`);
    }
    return `M${f1(x0)} ${f1(base + 4000)} L${pts.join(" L")} L${f1(x1)} ${f1(base + 4000)} Z`;
  }

  function buildDefs(host, geo, zoneYs) {
    const defs = svg("defs", {}, host);
    const grad = (id, attrs, stops) => {
      const g = svg("linearGradient", { id, ...attrs }, defs);
      stops.forEach(([o, c, a = 1]) => svg("stop", { offset: o, "stop-color": c, "stop-opacity": a }, g));
      return g;
    };
    const radial = (id, attrs, stops) => {
      const g = svg("radialGradient", { id, ...attrs }, defs);
      stops.forEach(([o, c, a = 1]) => svg("stop", { offset: o, "stop-color": c, "stop-opacity": a }, g));
    };
    const top = PEAK_Y - 1400;
    grad("jr-sky", { gradientUnits: "userSpaceOnUse", x1: 0, y1: top, x2: 0, y2: geo.H }, [
      [0, "#060b15"], [0.45, "#0e192b"], [0.72, "#1c2a42"], [0.9, "#36395a"], [1, "#4a3f55"],
    ]);
    radial("jr-dawn", {}, [[0, "#ffc28f", 0.42], [0.45, "#f19a74", 0.14], [1, "#f19a74", 0]]);
    grad("jr-far-a", { x1: 0, y1: 0, x2: 0, y2: 1 }, [[0, "#33415f"], [0.4, "#1f2a40"], [1, "#151d2e"]]);
    grad("jr-far-b", { x1: 0, y1: 0, x2: 0, y2: 1 }, [[0, "#2a3650"], [0.5, "#182131"], [1, "#111826"]]);

    // The face changes with altitude: meadow, summer grass, autumn rust, then bare winter rock.
    const y1 = PEAK_Y - 60;
    const y2 = geo.H;
    const o = (y) => clamp((y - y1) / (y2 - y1), 0, 1).toFixed(4);
    const [b1, b2, b3] = zoneYs;
    grad("jr-face", { gradientUnits: "userSpaceOnUse", x1: 0, y1, x2: 0, y2 }, [
      [0, "#6b768a"], [o(b3 - 40), "#56607a"], [o(b3 + 40), "#6a4a35"], [o(b2 - 40), "#6f4b2f"],
      [o(b2 + 40), "#55673a"], [o(b1 - 40), "#4f6838"], [o(b1 + 40), "#356049"], [1, "#203d31"],
    ]);
    grad("jr-snow", { gradientUnits: "userSpaceOnUse", x1: 0, y1: PEAK_Y - 60, x2: 0, y2: b3 + 40 }, [[0, "#f6f9fd"], [1, "#c3d1e2"]]);
    grad("jr-done", { gradientUnits: "userSpaceOnUse", x1: 0, y1: PEAK_Y, x2: 0, y2: geo.baseY }, [
      [o2(PEAK_Y + 60), ZONE_COLOR.final], [o2(PEAK_Y + 110), ZONE_COLOR.winter], [o2(b3), ZONE_COLOR.winter],
      [o2(b3 + 24), ZONE_COLOR.autumn], [o2(b2), ZONE_COLOR.autumn], [o2(b2 + 24), ZONE_COLOR.summer],
      [o2(b1), ZONE_COLOR.summer], [o2(b1 + 24), ZONE_COLOR.spring], [1, ZONE_COLOR.spring],
    ]);
    function o2(y) { return clamp((y - PEAK_Y) / (geo.baseY - PEAK_Y), 0, 1).toFixed(4); }
    radial("jr-cloud", {}, [[0, "#dfe7f3", 0.5], [0.6, "#dfe7f3", 0.18], [1, "#dfe7f3", 0]]);
    radial("jr-glow", {}, [[0, "#fff1c7", 0.55], [1, "#fff1c7", 0]]);
    grad("jr-beam", { x1: 0, y1: 0, x2: 1, y2: 0 }, [[0, "#fff3c4", 0.55], [1, "#fff3c4", 0]]);
    grad("jr-paint", { x1: 0, y1: 0, x2: 0, y2: 1 }, [[0, "#ffffff"], [0.6, "#e7ebef"], [1, "#b9c2cc"]]);
    const mask = svg("mask", { id: "jr-road-mask", maskUnits: "userSpaceOnUse", x: -1000, y: PEAK_Y - 1000, width: W + 2000, height: geo.H + 2000 }, defs);
    const clip = svg("clipPath", { id: "jr-mountain-clip" }, defs);
    return { mask, clip };
  }

  function silhouette(geo, rnd) {
    // Left and right edges of the main mountain, with rock noise; the tip leans a little east.
    const p = [rnd() * 6.28, rnd() * 6.28, rnd() * 6.28, rnd() * 6.28];
    const edge = (y, side) => {
      const noise = 16 * Math.sin(y / 63 + p[side > 0 ? 0 : 1]) + 9 * Math.sin(y / 23 + p[side > 0 ? 2 : 3]) + (rnd() - 0.5) * 7;
      return CX + side * (geo.half(y) + 70 + noise * clamp((y - PEAK_Y) / 140, 0, 1));
    };
    const tip = { x: CX + 26, y: PEAK_Y - 44 };
    const left = [];
    const right = [];
    for (let y = geo.H + 10; y > PEAK_Y + 10; y -= 26) {
      left.push([edge(y, -1), y]);
      right.unshift([edge(y, 1), y]);
    }
    left.push([CX - 70, PEAK_Y + 2], [CX - 30, PEAK_Y - 22], [CX - 6, PEAK_Y - 18]);
    right.unshift([CX + 48, PEAK_Y - 26], [CX + 92, PEAK_Y + 8]);
    const pts = [...left, [tip.x, tip.y], ...right];
    return { pts, tip, edge };
  }

  function render() {
    mapBox.textContent = "";
    M = null;
    if (!stops.length) return;

    const geo = layout(stops.length);
    const host = svg("svg", { role: "group", "aria-label": `${T.final_title} — ${stops.length}`, preserveAspectRatio: "xMidYMid slice" });
    mapBox.appendChild(host);
    const ends = measure(geo, host);
    const total = ends[ends.length - 1];
    const stopAt = placeStops(geo, ends, stops.length);

    // A scratch path for positions along the road.
    const probe = svg("path", { d: geo.d, fill: "none", stroke: "none" }, host);
    const pointAt = (l) => probe.getPointAtLength(clamp(l, 0, total));

    // Season boundaries: halfway between the last stop of a season and the first of the next; the last
    // one sits before the summit.
    const firstIndex = [];
    let n = 0;
    seasons.forEach((s, z) => { firstIndex[z] = n; n += s.stages.length; });
    const camps = seasons.map((s, z) => {
      const lastIdx = firstIndex[z] + s.stages.length - 1;
      const nextAt = z < seasons.length - 1 ? stopAt[firstIndex[z + 1]] : total - 70;
      const at = s.stages.length ? (stopAt[lastIdx] + nextAt) / 2 : nextAt;
      return { zone: z, at, point: pointAt(at) };
    });
    const zoneYs = camps.slice(0, 3).map((c) => c.point.y);
    while (zoneYs.length < 3) zoneYs.push(PEAK_Y + 200);
    const { mask, clip } = buildDefs(host, geo, zoneYs);
    const rnd = seeded(97);
    const sil = silhouette(geo, rnd);
    const mountainD = `M${sil.pts.map(([x, y]) => `${f1(x)} ${f1(y)}`).join(" L")} Z`;
    svg("path", { d: mountainD }, clip);

    // Sky, stars and the dawn behind the peak.
    svg("rect", { x: -4000, y: PEAK_Y - 4000, width: W + 8000, height: geo.H + 8000, fill: "url(#jr-sky)" }, host);
    const starsG = svg("g", { class: "jr-stars" }, host);
    for (let i = 0; i < 140; i++) {
      const c = svg("circle", { cx: f1(-900 + rnd() * (W + 1800)), cy: f1(PEAK_Y - 1100 + rnd() * 1300), r: f1(0.6 + rnd() * 1.5), opacity: f1(0.25 + rnd() * 0.6) }, starsG);
      if (i % 9 === 0) { c.classList.add("is-twinkle"); c.style.animationDelay = `${(rnd() * 4).toFixed(2)}s`; }
    }
    svg("ellipse", { cx: CX + 380, cy: PEAK_Y + 260, rx: 1100, ry: 780, fill: "url(#jr-dawn)" }, host);

    // Far ranges move slower than the camera (parallax).
    const farA = svg("g", { class: "jr-far" }, host);
    svg("path", { d: ridgeLine(seeded(11), -2600, W + 2600, geo.baseY - 120, 70, 900), fill: "url(#jr-far-a)" }, farA);
    const farB = svg("g", { class: "jr-far" }, host);
    svg("path", { d: ridgeLine(seeded(23), -2600, W + 2600, geo.H - 40, 60, 560), fill: "url(#jr-far-b)" }, farB);
    const cloudsBack = svg("g", {}, host);
    buildClouds(cloudsBack, geo, seeded(5), 5, 0.9);

    // The mountain: face, snow cap, rock strata, shaded east side.
    const mountain = svg("g", { class: "jr-mountain" }, host);
    svg("path", { d: mountainD, fill: "url(#jr-face)" }, mountain);
    const inside = svg("g", { "clip-path": "url(#jr-mountain-clip)" }, mountain);
    const snowY = zoneYs[2] + 20;
    const snowL = sil.edge(snowY, -1) - 40;
    const snowR = sil.edge(snowY, 1) + 40;
    let snowD = `M${f1(snowL)} ${f1(snowY)} L${f1(snowL)} ${PEAK_Y - 120} L${f1(snowR)} ${PEAK_Y - 120} L${f1(snowR)} ${f1(snowY)}`;
    for (let x = snowR; x > snowL; x -= 22 + rnd() * 26) {
      const drip = rnd() < 0.3 ? 30 + rnd() * 55 : rnd() * 16;
      snowD += ` L${f1(x - 6)} ${f1(snowY + drip)} L${f1(x - 14)} ${f1(snowY + rnd() * 8)}`;
    }
    svg("path", { d: snowD + " Z", fill: "url(#jr-snow)" }, inside);
    const strata = svg("g", { class: "jr-strata" }, inside);
    for (let y = PEAK_Y + 60; y < geo.H; y += 46 + rnd() * 40) {
      const a = rnd() * 6.28;
      let d = "";
      for (let x = -40; x <= W + 40; x += 60) d += `${x === -40 ? "M" : "L"}${x} ${f1(y + 10 * Math.sin(x / 130 + a) + 5 * Math.sin(x / 47 + a * 2))}`;
      svg("path", { d }, strata);
    }
    let ridge = `M${f1(sil.tip.x)} ${f1(sil.tip.y)}`;
    for (let y = sil.tip.y + 30; y <= geo.H + 20; y += 30) ridge += ` L${f1(sil.tip.x + (y - sil.tip.y) * 0.14 + 22 * Math.sin(y / 90) + (rnd() - 0.5) * 12)} ${f1(y)}`;
    svg("path", { class: "jr-shade", d: `${ridge} L${W + 400} ${geo.H + 20} L${W + 400} ${PEAK_Y - 200} Z` }, inside);
    svg("path", { class: "jr-rimlight", d: mountainD }, mountain);

    // Road samples, to keep trees off the asphalt.
    const samples = [];
    for (let l = 0; l <= total; l += 14) { const p = pointAt(l); samples.push([p.x, p.y]); }
    const clearOfRoad = (x, y, r) => samples.every(([sx, sy]) => (sx - x) * (sx - x) + (sy - y) * (sy - y) > r * r);

    // Season labels on the west flank, and trees in every season's band.
    const labels = svg("g", { class: "jr-zone-labels" }, host);
    const trees = svg("g", { class: "jr-trees", "clip-path": "url(#jr-mountain-clip)" }, host);
    const bands = seasons.map((s, z) => ({
      key: s.key,
      bottom: z === 0 ? geo.H - 20 : zoneYs[z - 1],
      top: z === 3 ? PEAK_Y + 90 : zoneYs[z],
    }));
    const altAt = (y) => ALT_BASE + ((geo.baseY - y) / (geo.baseY - geo.summit.y)) * (ALT_TOP - ALT_BASE);
    const treeList = [];
    bands.forEach((band, z) => {
      const mid = (band.top + band.bottom) / 2;
      const lx = sil.edge(mid, -1) - 26;
      const g = svg("g", { class: `jr-zone-label${seasons[z].unlocked ? "" : " is-locked"}`, transform: `translate(${f1(lx)} ${f1(mid)})` }, labels);
      svg("text", { class: "jr-zone-label__title", y: -6 }, g).textContent = seasons[z].title.toUpperCase();
      svg("text", { class: "jr-zone-label__meta", y: 16 }, g).textContent = `${meters(altAt(Math.min(band.bottom, geo.baseY)))} · ${T.bilet} ${seasons[z].stages[0] ? seasons[z].stages[0].n : ""}–${seasons[z].stages.length ? seasons[z].stages[seasons[z].stages.length - 1].n : ""}`;
      svg("line", { x1: 12, x2: 60, y1: 0, y2: 0 }, g);

      const tries = band.key === "winter" ? 90 : 200;
      for (let i = 0; i < tries; i++) {
        const y = band.top + rnd() * (band.bottom - band.top);
        const x = CX + (rnd() * 2 - 1) * (geo.half(y) + 40);
        if (y < PEAK_Y + 120) continue;
        const depth = 0.65 + 0.55 * ((y - PEAK_Y) / geo.span);
        const size = (8 + rnd() * 7) * depth;
        if (!clearOfRoad(x, y, 22 + size) || !clearOfRoad(x, y - size * 1.4, 20 + size)) continue;
        treeList.push({ x, y, size, kind: band.key, r: rnd() });
      }
    });
    treeList.sort((a, b) => a.y - b.y).forEach((t) => drawTree(trees, t));

    // The road, drawn in under a mask so it can grow on the first view.
    const maskPath = svg("path", { d: geo.d, fill: "none", stroke: "#fff", "stroke-width": 80, "stroke-linecap": "round", "stroke-dasharray": `${total} ${total}`, "stroke-dashoffset": 0 }, mask);
    const roadG = svg("g", { mask: "url(#jr-road-mask)" }, host);
    svg("path", { class: "jr-road-bank", d: geo.d, transform: "translate(0 7)" }, roadG);
    svg("path", { class: "jr-road-edge", d: geo.d }, roadG);
    const road = svg("path", { class: "jr-road", d: geo.d }, roadG);
    svg("path", { class: "jr-road-lane", d: geo.d }, roadG);
    const done = svg("path", { class: "jr-road-done", d: geo.d, "stroke-dasharray": `${total} ${total}`, "stroke-dashoffset": total }, host);

    // Start sign at the foot.
    const startG = svg("g", { class: "jr-start", transform: `translate(${f1(geo.start.x + 6)} ${f1(geo.start.y)})` }, host);
    svg("line", { x1: 0, y1: 0, x2: 0, y2: -46 }, startG);
    svg("rect", { x: -38, y: -74, width: 76, height: 30, rx: 5 }, startG);
    svg("text", { y: -63 }, startG).textContent = T.start_label.toUpperCase();
    svg("text", { class: "jr-start__alt", y: -50 }, startG).textContent = meters(ALT_BASE);

    // Camps between seasons: a tent, a pennant of the next season and a barrier across the road.
    const campNodes = camps.map((camp, z) => buildCamp(host, camp, z, pointAt, altAt));

    // Summit: a finish flag and the altitude.
    const summitG = svg("g", { class: `jr-summit${D.certified ? " is-won" : ""}${allDone ? " is-open" : ""}`, transform: `translate(${f1(geo.summit.x)} ${f1(geo.summit.y)})`, tabindex: 0, role: "button", "aria-label": T.final_title }, host);
    svg("circle", { class: "jr-summit__glow", r: 120, fill: "url(#jr-glow)" }, summitG);
    svg("line", { class: "jr-summit__pole", x1: 18, y1: 4, x2: 18, y2: -70 }, summitG);
    const cloth = svg("g", { class: "jr-summit__cloth", transform: "translate(18 -70)" }, summitG);
    for (let r = 0; r < 4; r++) for (let c = 0; c < 6; c++) svg("rect", { class: (r + c) % 2 ? "b" : "a", x: c * 7, y: r * 7, width: 7, height: 7 }, cloth);
    const plate = svg("g", { class: "jr-summit__plate", transform: "translate(18 -104)" }, summitG);
    svg("text", { y: 0 }, plate).textContent = T.finish.toUpperCase();
    svg("text", { class: "jr-summit__alt", y: 18 }, plate).textContent = meters(ALT_TOP);

    // Stops.
    const R = 15;
    const star = starPath(4.2);
    const nodes = stops.map((s, i) => {
      const p = pointAt(stopAt[i]);
      const shown = fresh.has(s.stage.id) ? starsBefore(s.stage.id) : s.stage.stars;
      const g = svg("g", {
        class: `jr-node ${nodeState(s, shown)}`.trim(), transform: `translate(${f1(p.x)} ${f1(p.y)})`,
        tabindex: 0, role: "button", "data-i": i, style: `--z:${ZONE_COLOR[s.season.key]}`,
        "aria-label": `${T.bilet} ${s.stage.n}${s.stage.cleared ? ` — ${T.cleared}, ${s.stage.stars} ${T.stars}` : ""}`,
      }, host);
      const body = svg("g", { class: "jr-node__body" }, g);
      svg("circle", { class: "jr-node__halo", r: R }, body);
      svg("circle", { class: "jr-node__ring", r: R }, body);
      svg("circle", { class: "jr-node__core", r: R - 5 }, body);
      svg("text", { class: "jr-node__num", y: 0.5 }, body).textContent = s.stage.n;
      const row = svg("g", { class: "jr-node__stars", transform: `translate(0 ${R + 9})` }, g);
      const stars = [-10, 0, 10].map((x) => svg("path", { d: star, transform: `translate(${x} 0)` }, row));
      const node = { ...s, i, g, body, stars, at: stopAt[i], point: p, shown };
      paintNode(node, shown);
      return node;
    });

    const fx = svg("g", { class: "jr-fx" }, host);
    const car = buildCar(host);
    const cloudsFront = svg("g", { class: "jr-clouds-front" }, host);
    buildClouds(cloudsFront, geo, seeded(77), 3, 0.5);

    const turns = [];
    geo.segs.forEach((s, i) => { if (s.kind === "turn" || s.kind === "summit") turns.push({ a: ends[i - 1], b: ends[i], slipped: false }); });

    M = {
      svg: host, geo, total, road, done, mask: maskPath, nodes, car, fx, camps: campNodes, turns, far: [farA, farB],
      summit: summitG, pointAt, altAt, zoneYs, carAt: 0, gap: 38,
      carState: { angle: 0, sx: 1, wheel: 0 },
    };
    return M;
  }

  function buildClouds(parent, geo, rnd, count, alpha) {
    for (let i = 0; i < count; i++) {
      const y = PEAK_Y + 40 + rnd() * (geo.baseY - PEAK_Y - 200);
      const x = rnd() < 0.5 ? -200 + rnd() * 500 : W - 300 + rnd() * 500;
      const g = svg("g", { class: "jr-cloud", opacity: alpha.toFixed(2) }, parent);
      g.style.animationDuration = `${50 + rnd() * 40}s`;
      g.style.animationDelay = `${-rnd() * 60}s`;
      const w = 160 + rnd() * 220;
      for (let k = 0; k < 5; k++) svg("ellipse", { cx: f1(x + (k - 2) * w * 0.22 + rnd() * 30), cy: f1(y + rnd() * 18), rx: f1(w * (0.3 + rnd() * 0.2)), ry: f1(20 + rnd() * 18), fill: "url(#jr-cloud)" }, g);
    }
  }

  function drawTree(parent, t) {
    const g = svg("g", { transform: `translate(${f1(t.x)} ${f1(t.y)})` }, parent);
    const s = t.size;
    svg("ellipse", { cx: 0, cy: 1, rx: f1(s * 0.9), ry: f1(s * 0.22), fill: "rgba(0,0,0,.28)" }, g);
    const pine = t.kind === "winter" || (t.kind !== "spring" && t.r < 0.3);
    if (pine) {
      const dark = t.kind === "winter" ? "#1d3833" : t.kind === "autumn" ? "#2b3a26" : "#1f4a35";
      svg("rect", { x: f1(-s * 0.09), y: f1(-s * 0.5), width: f1(s * 0.18), height: f1(s * 0.5), fill: "#3a2a20" }, g);
      [[1, 0.0], [0.78, 0.55], [0.55, 1.05]].forEach(([w, lift]) => {
        const base = -s * 0.35 - lift * s;
        svg("path", { d: `M${f1(-s * w)} ${f1(base)} L0 ${f1(base - s * 1.05)} L${f1(s * w)} ${f1(base)} Z`, fill: dark }, g);
        if (t.kind === "winter") svg("path", { d: `M${f1(-s * w * 0.42)} ${f1(base - s * 0.6)} L0 ${f1(base - s * 1.05)} L${f1(s * w * 0.42)} ${f1(base - s * 0.6)} Z`, fill: "#e9f0f8" }, g);
      });
      return;
    }
    const palette = {
      spring: [["#6f9d62", "#86b676"], ["#c78d9f", "#e7b3c3"], ["#7da86c", "#9cc58a"], ["#d39aac", "#f0c7d3"]],
      summer: [["#24553a", "#31704a"], ["#2c6240", "#3f7f4f"], ["#335f33", "#477a40"]],
      autumn: [["#a8512a", "#c96a33"], ["#8f3d27", "#b14d2f"], ["#b9812e", "#d9a043"], ["#9b5f2b", "#c27a35"]],
    }[t.kind];
    const [dark, light] = palette[Math.floor(t.r * palette.length) % palette.length];
    svg("rect", { x: f1(-s * 0.08), y: f1(-s * 0.9), width: f1(s * 0.16), height: f1(s * 0.9), fill: "#3b2b22" }, g);
    const cy = -s * 1.35;
    [[-0.42, 0.12, 0.62], [0.4, 0.1, 0.6], [0, -0.32, 0.72]].forEach(([dx, dy, r]) => svg("circle", { cx: f1(dx * s + s * 0.08), cy: f1(cy + dy * s + s * 0.1), r: f1(r * s), fill: dark }, g));
    [[-0.42, 0.12, 0.55], [0.4, 0.1, 0.52], [0, -0.32, 0.64]].forEach(([dx, dy, r]) => svg("circle", { cx: f1(dx * s - s * 0.04), cy: f1(cy + dy * s - s * 0.06), r: f1(r * s), fill: light }, g));
  }

  function buildCamp(host, camp, z, pointAt, altAt) {
    const p = camp.point;
    const a = pointAt(camp.at - 2);
    const b = pointAt(camp.at + 2);
    const dir = b.x >= a.x ? 1 : -1;
    const nextLocked = z < seasons.length - 1 ? !seasons[z + 1].unlocked : !allDone;
    const justOpened = seasonsJustDone.includes(seasons[z].key);
    const closed = nextLocked || justOpened;
    const nextKey = ORDER[z + 1];
    const g = svg("g", { class: "jr-camp", transform: `translate(${f1(p.x)} ${f1(p.y)})`, style: `--z:${ZONE_COLOR[nextKey]}` }, host);

    // Tent and pennant sit uphill of the road, the barrier on it.
    const tent = svg("g", { class: "jr-camp__tent", transform: `translate(${-dir * 34} -30)` }, g);
    svg("path", { d: "M-20 0 L0 -26 L20 0 Z", class: "jr-camp__canvas" }, tent);
    svg("path", { d: "M-4 0 L0 -26 L4 0 Z", class: "jr-camp__door" }, tent);
    const pole = svg("g", { transform: `translate(${-dir * 6} -26)` }, g);
    svg("line", { x1: 0, y1: 0, x2: 0, y2: -40, class: "jr-camp__pole" }, pole);
    svg("path", { d: "M0 -40 L22 -34 L0 -28 Z", class: "jr-camp__pennant" }, pole);
    if (z < 3) {
      const plate = svg("g", { class: "jr-camp__plate", transform: `translate(${-dir * 34} -64)` }, g);
      svg("text", { y: 0 }, plate).textContent = (byKey[nextKey] ? byKey[nextKey].title : "").toUpperCase();
      svg("text", { class: "jr-camp__alt", y: 13 }, plate).textContent = meters(altAt(p.y));
    }

    const gate = svg("g", { class: "jr-gate-bar", transform: `translate(${dir * 16} 0)` }, g);
    svg("rect", { x: -2.5, y: -22, width: 5, height: 22, rx: 1.5, class: "jr-gate-bar__post" }, gate);
    const arm = svg("g", { class: "jr-gate-bar__arm" }, gate);
    const len = 40;
    svg("rect", { x: dir > 0 ? -len : 0, y: -21, width: len, height: 5, rx: 2.5, class: "jr-gate-bar__beam" }, arm);
    for (let i = 0; i < 4; i++) svg("rect", { x: (dir > 0 ? -len : 0) + 4 + i * 10, y: -21, width: 5, height: 5, class: "jr-gate-bar__stripe" }, arm);
    svg("circle", { cx: 0, cy: -18.5, r: 3, class: "jr-gate-bar__hub" }, gate);
    const setOpen = (open) => arm.setAttribute("transform", open ? `rotate(${dir > 0 ? 78 : -78} 0 -18.5)` : "rotate(0 0 -18.5)");
    setOpen(!closed);
    return { ...camp, g, arm, dir, open: !closed, justOpened, setOpen };
  }

  function buildCar(parent) {
    // Side view of the school's white hatchback with a green stripe and a roof sign. Faces +x.
    const car = svg("g", { class: "jr-car" }, parent);
    svg("ellipse", { class: "jr-car__shadow", cx: 2, cy: 2, rx: 27, ry: 3.4 }, car);
    svg("path", { class: "jr-car__beam", d: "M28 -15 L120 -34 L120 6 Z" }, car);
    const body = svg("g", { class: "jr-car__body" }, car);
    const shell = svg("g", { class: "jr-car__shell" }, body);
    svg("path", { class: "jr-car__paint", d: "M-27 -7 L-27 -17 Q-27 -21 -23 -22 L-14 -23 L-7 -32 Q-5 -34 -1 -34 L12 -34 Q16 -34 18 -31 L24 -23 L28 -22 Q31 -21 31 -17 L31 -8 Q31 -6 29 -6 L-25 -6 Q-27 -6 -27 -7 Z" }, shell);
    svg("path", { class: "jr-car__glass", d: "M-11 -23 L-5.5 -31 L3 -31 L3 -23 Z" }, shell);
    svg("path", { class: "jr-car__glass", d: "M6 -23 L6 -31 L12 -31 Q14 -31 15 -29 L19 -23 Z" }, shell);
    svg("path", { class: "jr-car__glint", d: "M-8 -24 L-4 -30 L-1.5 -30 L-5.5 -24 Z" }, shell);
    svg("rect", { class: "jr-car__stripe", x: -26, y: -16, width: 56, height: 3 }, shell);
    svg("rect", { class: "jr-car__sign", x: -4, y: -40, width: 14, height: 6, rx: 1.5 }, shell);
    svg("rect", { class: "jr-car__light", x: 28, y: -20, width: 3, height: 4, rx: 1 }, shell);
    svg("rect", { class: "jr-car__tail", x: -27.5, y: -20, width: 2.6, height: 4.5, rx: 1 }, shell);
    svg("line", { class: "jr-car__seam", x1: 4.5, y1: -22, x2: 4.5, y2: -8 }, shell);
    const wheels = [-15, 18].map((x) => {
      const w = svg("g", { class: "jr-car__wheel", transform: `translate(${x} -6)` }, car);
      svg("circle", { class: "jr-car__tire", r: 6.6 }, w);
      svg("circle", { class: "jr-car__rim", r: 3.8 }, w);
      const spokes = svg("g", { class: "jr-car__spokes" }, w);
      for (let i = 0; i < 5; i++) svg("line", { x1: 0, y1: 0, x2: 0, y2: -3.6, transform: `rotate(${i * 72})` }, spokes);
      return { g: w, x, spokes };
    });
    car.wheels = wheels;
    car.body = body;
    return car;
  }

  function nodeState(s, shownStars) {
    if (!s.season.unlocked) return "is-locked";
    if (shownStars > 0) return "is-cleared";
    return s.stage.id === s.season.current ? "is-current" : "";
  }

  function paintNode(node, stars) {
    node.stars.forEach((path, i) => path.classList.toggle("is-on", i < stars));
  }

  // ---------- Camera ----------
  // The camera is the SVG viewBox: a centre and a visible width; the height follows the box.
  const cam = { x: CX, y: 0, w: 1000 };
  let camToken = 0;
  let follow = false;
  let hudKey = null;

  function boxSize() { return { cw: mapBox.clientWidth || 1, ch: mapBox.clientHeight || 1 }; }
  function closeW() { const { cw } = boxSize(); return cw < 640 ? 540 : clamp(cw * 0.95, 820, 1150); }
  function overviewCam() {
    const { cw, ch } = boxSize();
    const w = Math.max(W - 40, (M.geo.H - PEAK_Y + 330) * (cw / ch));
    return { x: CX, y: M.geo.H - (w * ch / cw) / 2 + 10, w };
  }
  function isOverview() { return M && cam.w > overviewCam().w * 0.8; }

  function applyCam() {
    if (!M) return;
    const { cw, ch } = boxSize();
    const h = cam.w * ch / cw;
    const minX = -320;
    const maxX = W + 320;
    const minY = PEAK_Y - 700;
    const maxY = M.geo.H + 10;
    cam.x = cam.w >= maxX - minX ? CX : clamp(cam.x, minX + cam.w / 2, maxX - cam.w / 2);
    cam.y = h >= maxY - minY ? maxY - h / 2 : clamp(cam.y, minY + h / 2, maxY - h / 2);
    M.svg.setAttribute("viewBox", `${f1(cam.x - cam.w / 2)} ${f1(cam.y - h / 2)} ${f1(cam.w)} ${f1(h)}`);
    const midY = (M.geo.baseY + PEAK_Y) / 2;
    M.far[0].setAttribute("transform", `translate(${f1((cam.x - CX) * 0.55)} ${f1((cam.y - midY) * 0.62)})`);
    M.far[1].setAttribute("transform", `translate(${f1((cam.x - CX) * 0.32)} ${f1((cam.y - midY) * 0.36)})`);
    onCamera();
  }

  function flyTo(target, ms = 1200) {
    const token = ++camToken;
    const from = { ...cam };
    const lw0 = Math.log(from.w);
    const lw1 = Math.log(target.w);
    return tween(ms, (t) => {
      if (token !== camToken) return false;
      const e = easeInOut(t);
      // Zoom out a little mid-flight on long moves, like a real camera crane.
      const lift = Math.min(0.35, Math.hypot(target.x - from.x, target.y - from.y) / 4000) * Math.sin(Math.PI * e);
      cam.x = from.x + (target.x - from.x) * e;
      cam.y = from.y + (target.y - from.y) * e;
      cam.w = Math.exp(lw0 + (lw1 - lw0) * e) * (1 + lift);
      applyCam();
      return true;
    });
  }

  function camAt(at, w = closeW()) {
    const p = M.pointAt(at);
    const { cw, ch } = boxSize();
    return { x: p.x, y: p.y - (w * ch / cw) * 0.06, w };
  }

  function zoneOfY(y) {
    if (!M) return 0;
    let z = 0;
    while (z < 3 && y < M.zoneYs[z]) z += 1;
    if (z === 3 && y < M.geo.summit.y + 70) return 4;
    return z;
  }

  function onCamera() {
    const key = isOverview() ? (D.active === "final" ? "final" : D.active) : ORDER[zoneOfY(cam.y)];
    if (key !== hudKey) {
      hudKey = key;
      scene.dataset.season = key;
      updateHud(key);
      particles.set(key);
      tabs.forEach((tab) => {
        const on = tab.dataset.season === key;
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
      });
    }
    railView();
  }

  // ---------- Car ----------
  function carToWorld(lx, ly) {
    const { x, y, angle, sx } = M.carState;
    const a = (angle * Math.PI) / 180;
    const px = lx * sx;
    return { x: x + px * Math.cos(a) - ly * Math.sin(a), y: y + px * Math.sin(a) + ly * Math.cos(a) };
  }

  function placeCar(at, dt = 1, bounce = 0) {
    if (!M) return null;
    const len = clamp(at, 0.5, M.total - 0.5);
    const p = M.pointAt(len);
    const a = M.pointAt(len - 2);
    const b = M.pointAt(len + 2);
    const tx = b.x - a.x;
    const ty = b.y - a.y;
    const norm = Math.hypot(tx, ty) || 1;
    const cos = tx / norm;
    // Side view: the car turns around at the hairpins by narrowing through zero, and tilts with the
    // slope (never past ~30°, so it climbs rather than flips).
    const targetSx = Math.sign(cos || 1) * Math.max(0.16, Math.abs(cos));
    const targetAngle = clamp((Math.atan2(ty, Math.abs(tx) + 1e-6) * 180) / Math.PI, -32, 32) * Math.sign(cos || 1);
    const st = M.carState;
    const k = Math.min(1, dt * 9);
    st.sx += (targetSx - st.sx) * k;
    st.angle += (targetAngle - st.angle) * k;
    st.x = p.x;
    st.y = p.y;
    st.wheel += ((at - M.carAt) / 6.6) * (180 / Math.PI) * Math.sign(st.sx || 1);
    M.car.setAttribute("transform", `translate(${f1(p.x)} ${f1(p.y)}) rotate(${st.angle.toFixed(2)}) scale(${st.sx.toFixed(3)} 1)`);
    M.car.body.setAttribute("transform", `translate(0 ${bounce.toFixed(2)})`);
    M.car.wheels.forEach((w) => w.spokes.setAttribute("transform", `rotate(${st.wheel.toFixed(1)})`));
    M.done.setAttribute("stroke-dashoffset", f1(M.total - at));
    M.carAt = at;
    return p;
  }

  function puff(strength = 1) {
    if (reduced || !M) return;
    const o = carToWorld(-29, -9);
    const back = carToWorld(-60, -22);
    const dx = (back.x - o.x) * 0.5;
    const dy = (back.y - o.y) * 0.5 - 10;
    const c = svg("circle", { class: "jr-puff", cx: f1(o.x), cy: f1(o.y), r: f1(2.6 * strength) }, M.fx);
    c.animate([
      { transform: "translate(0,0) scale(1)", opacity: 0.5 * strength },
      { transform: `translate(${f1(dx)}px, ${f1(dy)}px) scale(${(2.6 + strength).toFixed(2)})`, opacity: 0 },
    ], { duration: 1100 + Math.random() * 400, easing: "cubic-bezier(.2,.7,.3,1)" }).onfinish = () => c.remove();
  }

  function dust(count, zone) {
    if (reduced || !M) return;
    const color = ["#9c8a68", "#a28d5f", "#9a6a43", "#eef4fb"][zone] || "#9c8a68";
    const o = carToWorld(-15, 0);
    const back = carToWorld(-40, 0);
    const bx = (back.x - o.x) / 25;
    for (let i = 0; i < count; i++) {
      const c = svg("circle", { class: "jr-dust", cx: f1(o.x), cy: f1(o.y), r: f1(0.8 + Math.random() * 1.6), fill: color }, M.fx);
      const vx = bx * (14 + Math.random() * 26);
      const vy = -(8 + Math.random() * 18);
      const frames = [0, 0.33, 0.66, 1].map((t) => ({
        transform: `translate(${f1(vx * t)}px, ${f1(vy * t + 34 * t * t)}px)`, opacity: 0.9 * (1 - t),
      }));
      c.animate(frames, { duration: 520 + Math.random() * 300, easing: "linear" }).onfinish = () => c.remove();
    }
  }

  let idleTimer = null;
  function idle(on) {
    if (!M) return;
    M.car.classList.toggle("is-idle", on);
    clearInterval(idleTimer);
    idleTimer = null;
    if (on && !reduced) {
      idleTimer = setInterval(() => {
        if (!alive()) { clearInterval(idleTimer); return; }
        if (!document.hidden && sceneVisible) puff(0.7);
      }, 1500);
    }
  }

  function youAreHere(show) {
    if (!M) return;
    M.svg.querySelectorAll(".jr-youare").forEach((n) => n.remove());
    if (!show || !M.car) return;
    const st = M.carState;
    const text = `${T.you} · ${meters(M.altAt(st.y))}`;
    const w = text.length * 6.1 + 22;
    const g = svg("g", { class: "jr-youare", transform: `translate(${f1(st.x)} ${f1(st.y - 62)})` }, M.svg);
    svg("rect", { x: f1(-w / 2), y: -11, width: f1(w), height: 22, rx: 11 }, g);
    svg("path", { d: "M-5 10 L0 16 L5 10 Z" }, g);
    svg("text", { y: 0.5 }, g).textContent = text;
    if (!reduced) g.animate([{ opacity: 0, transform: `translate(${f1(st.x)}px, ${f1(st.y - 52)}px)` }, { opacity: 1, transform: `translate(${f1(st.x)}px, ${f1(st.y - 62)}px)` }], { duration: 480, easing: "cubic-bezier(.22,1,.36,1)" });
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
    particles.burst(rect.left + rect.width / 2 - box.left, rect.top + rect.height / 2 - box.top, 22);
    setTimeout(() => node.g.classList.remove("is-burst"), 800);
  }

  // Where the car parks: just below the first unfinished stop of an open season, or at the summit.
  function parking(starsOf) {
    if (!M) return 0;
    const next = M.nodes.find((n) => n.season.unlocked && starsOf(n.stage.id) === 0);
    if (next) return Math.max(0, next.at - M.gap);
    return allDone ? M.total - 30 : M.camps[M.camps.length - 1].at - 30;
  }

  // The climb. Speed drops on steep ground, in hairpins and with altitude; the engine strains in
  // pulses, and on some hairpins the wheels spin and the car slides back before it bites again.
  let driving = false;
  async function drive(from, to) {
    if (!M || to <= from + 1) { placeCar(to); return; }
    driving = true;
    idle(false);
    youAreHere(false);
    const BASE = 165;
    const boost = Math.max(1, (to - from) / (BASE * 6.5));
    const vmax = BASE * boost;
    const brake = 260 * boost;
    const pending = M.nodes.filter((n) => n.shown < n.stage.stars);
    M.turns.forEach((t) => { t.slipped = false; });
    let slips = 0;
    let at = from;
    let v = 0;
    let phase = null; // { kind: "slip"|"push", until }
    let lastPuff = 0;
    let lastDust = 0;
    let clock = 0;

    await new Promise((resolve) => {
      let prev = performance.now();
      const started = prev;
      const frame = (now) => {
        if (!alive()) return resolve();
        const dt = Math.min(0.05, (now - prev) / 1000);
        prev = now;
        clock += dt;
        const p0 = M.pointAt(at);
        const p1 = M.pointAt(at + 3);
        const len = Math.hypot(p1.x - p0.x, p1.y - p0.y) || 1;
        const steep = clamp(-(p1.y - p0.y) / len, 0, 1);
        const turning = 1 - Math.abs(p1.x - p0.x) / len;
        const altitude = clamp((M.geo.baseY - p0.y) / M.geo.span, 0, 1);
        const pulse = 0.8 + 0.2 * Math.sin(clock * 5.2) * Math.sin(clock * 1.7 + 1);
        let target = vmax * (1 - 0.42 * steep) * (1 - 0.3 * turning) * (1 - 0.22 * altitude) * pulse;

        const turn = M.turns.find((t) => at > t.a + (t.b - t.a) * 0.4 && at < t.b);
        if (turn && !turn.slipped && !phase && slips < 3 && (to - at) > 60 && boost < 3) {
          turn.slipped = true;
          if ((M.turns.indexOf(turn) + slips) % 2 === 0) {
            slips += 1;
            phase = { kind: "slip", until: clock + 0.42 };
            dust(9, zoneOfY(p0.y));
          }
        }
        if (phase && clock > phase.until) phase = phase.kind === "slip" ? { kind: "push", until: clock + 0.55 } : null;
        if (phase && phase.kind === "slip") target = -38;
        if (phase && phase.kind === "push") target = vmax * 0.95;

        const remaining = to - at;
        target = Math.min(target, Math.sqrt(2 * brake * Math.max(0, remaining)) + 4);
        v += (target - v) * Math.min(1, dt * (phase && phase.kind === "slip" ? 6 : 2.6));
        at = clamp(at + v * dt, from - 25, to);

        const strain = phase ? 1 : clamp(0.3 + steep * 0.9 + turning * 0.4, 0, 1);
        const bounce = Math.sin(clock * 38) * 0.35 * strain + (phase && phase.kind === "slip" ? (Math.random() - 0.5) * 1.6 : 0);
        placeCar(at, dt, bounce);
        if (now - lastPuff > (phase ? 110 : 360 - 200 * strain)) { puff(0.6 + strain * 0.5); lastPuff = now; }
        if ((phase || steep > 0.45) && now - lastDust > (phase ? 70 : 240)) { dust(phase ? 3 : 1, zoneOfY(p0.y)); lastDust = now; }

        pending.forEach((n) => { if (n.shown < n.stage.stars && at >= n.at - 6) clearNode(n); });
        M.camps.forEach((c) => {
          if (c.justOpened && !c.open && at >= c.at - 70) { c.open = true; c.g.classList.add("is-lifting"); c.setOpen(true); }
        });
        hud.alt.textContent = Math.round(M.altAt(p0.y)).toLocaleString("ru-RU");
        railCar(at);

        if (follow) {
          const { cw, ch } = boxSize();
          const h = cam.w * ch / cw;
          const ahead = Math.sign(M.carState.sx) * cam.w * 0.1;
          cam.x += (p0.x + ahead - cam.x) * Math.min(1, dt * 2.4);
          cam.y += (p0.y - h * 0.1 - cam.y) * Math.min(1, dt * 2.4);
          applyCam();
        }

        const finished = remaining < 0.6 && Math.abs(v) < 8;
        if (finished || now - started > 14000) { at = to; placeCar(to, 1); return resolve(); }
        requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
    });
    // Stages cleared out of order (further than the car went) light up when it arrives.
    pending.forEach((n) => { if (n.shown < n.stage.stars) clearNode(n); });
    M.camps.forEach((c) => { if (c.justOpened && !c.open) { c.open = true; c.setOpen(true); } });
    M.nodes.forEach((n) => n.g.classList.toggle("is-current", n.season.unlocked && n.stage.id === n.season.current));
    driving = false;
  }

  // ---------- Progress rail ----------
  let rail = null;
  function buildRail() {
    railBox.textContent = "";
    if (!M) return;
    const n = stops.length;
    const cleared = D.cleared;
    const pct = n ? Math.round((cleared * 100) / n) : 0;
    railBox.innerHTML = `
      <div class="jr-rail__end"><i class="ti ti-flag-3"></i><b>${esc(T.finish)}</b><small>${esc(meters(ALT_TOP))}</small></div>
      <div class="jr-rail__track" role="presentation">
        ${M.camps.map((c, z) => {
          const a = z ? M.camps[z - 1].at : 0;
          return `<span class="jr-rail__zone${seasons[z].unlocked ? "" : " is-locked"}" data-z="${z}" style="--a:${(a / M.total) * 100}%;--b:${(c.at / M.total) * 100}%;--c:${ZONE_COLOR[seasons[z].key]}" title="${esc(seasons[z].title)}"></span>`;
        }).join("")}
        <span class="jr-rail__fill"></span>
        <span class="jr-rail__view"></span>
        <span class="jr-rail__car"><i class="ti ti-car"></i></span>
      </div>
      <div class="jr-rail__stat"><b>${pct}%</b><small>${esc(T.passed)}</small></div>`;
    if (hud.left) hud.left.textContent = Math.max(0, n - cleared);
    rail = {
      track: railBox.querySelector(".jr-rail__track"),
      fill: railBox.querySelector(".jr-rail__fill"),
      car: railBox.querySelector(".jr-rail__car"),
      view: railBox.querySelector(".jr-rail__view"),
    };
    rail.track.addEventListener("click", (event) => {
      if (!M) return;
      const r = rail.track.getBoundingClientRect();
      const frac = clamp(1 - (event.clientY - r.top) / r.height, 0, 1);
      follow = false;
      flyTo(camAt(frac * M.total), 900);
    });
  }
  function railCar(at) {
    if (!rail || !M) return;
    const f = clamp(at / M.total, 0, 1) * 100;
    rail.fill.style.height = `${f}%`;
    rail.car.style.bottom = `${f}%`;
  }
  function railView() {
    if (!rail || !M) return;
    // The camera's vertical window, mapped onto the rail by the arc length at those heights.
    const { cw, ch } = boxSize();
    const h = cam.w * ch / cw;
    const arcAtY = (y) => {
      const n = M.nodes;
      if (!n.length) return 0;
      if (y >= n[0].point.y) return 0;
      for (let i = 1; i < n.length; i++) if (n[i].point.y < y) return n[i - 1].at;
      return y <= M.geo.summit.y ? M.total : n[n.length - 1].at;
    };
    const lo = arcAtY(cam.y + h / 2) / M.total;
    const hi = arcAtY(cam.y - h / 2) / M.total;
    rail.view.style.bottom = `${lo * 100}%`;
    rail.view.style.height = `${Math.max(3, (hi - lo) * 100)}%`;
  }

  // ---------- Stage card ----------
  function closePop() {
    pop.hidden = true;
    pop.textContent = "";
  }

  function openPop(node) {
    const { stage, season } = node;
    const next = stage.id === season.current;
    const status = !season.unlocked
      ? `<span class="jr-pop__status"><i class="ti ti-lock"></i>${esc(T.locked)}</span>`
      : stage.cleared
        ? `<span class="jr-pop__status is-ok"><i class="ti ti-circle-check"></i>${esc(T.cleared)}</span>`
        : next ? `<span class="jr-pop__status is-next"><i class="ti ti-target"></i>${esc(T.next)}</span>`
          : `<span class="jr-pop__status"><i class="ti ti-circle-dashed"></i>${esc(T.open)}</span>`;
    const stars = [0, 1, 2].map((i) => `<span class="${i < stage.stars ? "is-on" : ""}">★</span>`).join("");
    const url = D.start_url.replace(/\/0\/(?=[^/]*$)/, `/${stage.id}/`);
    pop.innerHTML = `
      <div class="jr-pop__head"><b>${esc(T.bilet)} ${stage.n}</b><em>${esc(season.title)} · ${esc(meters(M.altAt(node.point.y)))}</em>
        <button type="button" class="jr-pop__close" aria-label="${esc(T.close)}"><i class="ti ti-x"></i></button></div>
      ${status}
      <div class="jr-pop__stars" aria-label="${stage.stars} ${esc(T.stars)}">${stars}</div>
      <div class="jr-pop__grid">
        <div><small>${esc(T.best)}</small><b>${stage.best === null ? "—" : `${stage.best}%`}</b></div>
        <div><small>${esc(T.attempts)}</small><b>${stage.attempts}</b></div>
      </div>
      <p class="jr-pop__rule">${esc(!season.unlocked ? lockMessage(season) : stage.stars === 3 ? T.perfect : T.rule)}</p>
      ${season.unlocked ? `<a class="jr-btn jr-btn--primary" href="${url}"><i class="ti ti-player-play"></i>${esc(stage.attempts ? T.again : T.start)}</a>` : ""}`;
    pop.hidden = false;

    const box = scene.getBoundingClientRect();
    const r = node.body.getBoundingClientRect();
    const cx = r.left + r.width / 2 - box.left;
    const width = pop.offsetWidth;
    const height = pop.offsetHeight;
    const left = Math.max(12, Math.min(box.width - width - 12, cx - width / 2));
    const above = r.top - box.top - height - 14;
    const top = above > 12 ? above : Math.min(box.height - height - 12, r.bottom - box.top + 26);
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
    pop.style.setProperty("--ox", `${cx - left}px`);
    pop.style.setProperty("--oy", above > 12 ? "100%" : "0%");
    pop.querySelector(".jr-pop__close").addEventListener("click", closePop);
    const action = pop.querySelector("a") || pop.querySelector(".jr-pop__close");
    action.focus({ preventScroll: true });
  }

  function lockMessage(season) {
    const previous = seasons[seasons.indexOf(season) - 1];
    if (!previous) return T.locked;
    const done = previous.stages.filter((st) => st.cleared).length;
    return `${T.locked}: ${previous.title} — ${done}/${previous.stages.length}`;
  }

  // ---------- Pointer: drag to look around, click a stop ----------
  let drag = null;
  let suppressClick = false;
  mapBox.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || !M) return;
    drag = { x: event.clientX, y: event.clientY, cx: cam.x, cy: cam.y, moved: false, id: event.pointerId };
  });
  mapBox.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (!drag.moved) {
      if (Math.hypot(dx, dy) < 6) return;
      drag.moved = true;
      camToken += 1;
      follow = false;
      closePop();
      mapBox.setPointerCapture(drag.id);
      mapBox.classList.add("is-dragging");
    }
    const scale = cam.w / boxSize().cw;
    cam.x = drag.cx - dx * scale;
    cam.y = drag.cy - dy * scale;
    applyCam();
  });
  const endDrag = () => {
    if (!drag) return;
    if (drag.moved) { suppressClick = true; setTimeout(() => { suppressClick = false; }, 0); }
    mapBox.classList.remove("is-dragging");
    drag = null;
  };
  mapBox.addEventListener("pointerup", endDrag);
  mapBox.addEventListener("pointercancel", endDrag);

  mapBox.addEventListener("click", (event) => {
    if (suppressClick || !M) return;
    if (event.target.closest(".jr-summit")) { event.stopPropagation(); openFinal(); return; }
    const g = event.target.closest(".jr-node");
    if (!g) return;
    event.stopPropagation();
    openPop(M.nodes[Number(g.dataset.i)]);
  });
  mapBox.addEventListener("keydown", (event) => {
    const g = event.target.closest(".jr-node, .jr-summit");
    if (!g || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    g.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  mapBox.addEventListener("focusin", (event) => {
    const g = event.target.closest(".jr-node");
    if (!g || !M || drag) return;
    const r = g.getBoundingClientRect();
    const box = mapBox.getBoundingClientRect();
    if (r.top < box.top + 70 || r.bottom > box.bottom - 70 || r.left < box.left + 40 || r.right > box.right - 90) {
      flyTo(camAt(M.nodes[Number(g.dataset.i)].at, Math.min(cam.w, closeW())), 500);
    }
  });
  scene.addEventListener("click", (event) => { if (!pop.hidden && !pop.contains(event.target)) closePop(); });
  const onKey = (event) => {
    if (!alive()) { document.removeEventListener("keydown", onKey); return; }
    if (event.key === "Escape") { closePop(); if (!finalBox.hidden) closeFinal(); }
  };
  document.addEventListener("keydown", onKey);

  // ---------- Weather (canvas, in front of the mountain) ----------
  let sceneVisible = true;
  const particles = (() => {
    const ctx = canvas.getContext("2d");
    const kinds = {
      spring: { colors: ["#f6c7d6", "#f1a9c0", "#ecfccb", "#ffffff"], shape: "petal", fall: 0.25, drift: 0.35, size: [1.8, 3.6], alpha: [0.25, 0.6], count: 40 },
      summer: { colors: ["#fde68a", "#fbbf24", "#fff7d6"], shape: "mote", fall: -0.12, drift: 0.08, size: [0.8, 2], alpha: [0.2, 0.6], count: 34 },
      autumn: { colors: ["#e07a35", "#c4542a", "#b7832f", "#e9a646"], shape: "leaf", fall: 0.55, drift: 0.45, size: [2.6, 4.8], alpha: [0.45, 0.85], count: 36 },
      winter: { colors: ["#ffffff", "#e6f1ff", "#dbe7f7"], shape: "snow", fall: 0.7, drift: 0.3, size: [0.8, 2.6], alpha: [0.4, 0.9], count: 90 },
      final: { colors: ["#fde68a", "#e9c46a", "#ffffff"], shape: "mote", fall: -0.06, drift: 0.05, size: [0.8, 2], alpha: [0.2, 0.8], count: 40 },
    };
    let kind = kinds.spring;
    let flakes = [];
    let bursts = [];
    let w = 0;
    let h = 0;
    let running = false;

    const rand = (a, b) => a + Math.random() * (b - a);
    function spawn(anywhere) {
      return {
        x: rand(0, w), y: anywhere ? rand(0, h) : (kind.fall > 0 ? -10 : h + 10),
        r: rand(kind.size[0], kind.size[1]), a: rand(kind.alpha[0], kind.alpha[1]),
        vy: kind.fall * rand(0.5, 1.4), vx: rand(-kind.drift, kind.drift),
        rot: rand(0, 6.28), spin: rand(-0.03, 0.03), phase: rand(0, 6.28),
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
      const count = Math.min(kind.count, Math.round((w * h) / 9000));
      flakes = Array.from({ length: count }, () => spawn(true));
    }
    function drawFlake(p, t) {
      ctx.globalAlpha = p.a * (kind.shape === "mote" ? 0.6 + 0.4 * Math.sin(t / 700 + p.phase) : 1);
      ctx.fillStyle = p.color;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.beginPath();
      if (kind.shape === "leaf") ctx.ellipse(0, 0, p.r, p.r * 0.42, 0, 0, Math.PI * 2);
      else if (kind.shape === "petal") ctx.ellipse(0, 0, p.r, p.r * 0.62, 0, 0, Math.PI * 2);
      else ctx.arc(0, 0, p.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    function frame(t) {
      if (!alive() || !sceneVisible || document.hidden) { running = false; return; }
      ctx.clearRect(0, 0, w, h);
      flakes.forEach((p, i) => {
        p.x += p.vx + Math.sin(t / 1400 + p.phase) * kind.drift * 0.7;
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
      new IntersectionObserver(([entry]) => { sceneVisible = entry.isIntersecting; if (sceneVisible) start(); }).observe(scene);
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

  // ---------- HUD ----------
  function updateHud(key) {
    const index = ORDER.indexOf(key);
    if (key === "final") {
      hud.index.textContent = `05 · ${T.finish}`;
      hud.title.textContent = T.final_title;
      hud.motto.textContent = T.final_motto;
      hud.stars.textContent = `${seasons.reduce((n, s) => n + s.stars, 0)}/${seasons.reduce((n, s) => n + s.max_stars, 0)}`;
      return;
    }
    const s = byKey[key];
    if (!s) return;
    hud.index.textContent = `${T.season_label} 0${index + 1} / 0${seasons.length}`;
    hud.title.textContent = s.title;
    hud.motto.textContent = `${s.motto} · ${s.stages.filter((st) => st.cleared).length}/${s.stages.length}`;
    hud.stars.textContent = `${s.stars}/${s.max_stars}`;
  }

  // ---------- Final: the summit panel ----------
  async function openFinal() {
    if (!M) return;
    closePop();
    follow = false;
    await flyTo({ x: M.geo.summit.x, y: M.geo.summit.y + 40, w: closeW() * 0.9 }, 900);
    if (!alive()) return;
    finalBox.hidden = false;
    scene.classList.add("is-final");
    const focusable = finalBox.querySelector(".jr-final__close");
    if (focusable) focusable.focus({ preventScroll: true });
  }
  function closeFinal() {
    finalBox.hidden = true;
    scene.classList.remove("is-final");
  }
  finalBox.querySelectorAll("[data-jr-close-final]").forEach((b) => b.addEventListener("click", closeFinal));

  function showZone(key) {
    if (!M) return;
    closePop();
    if (key === "final") { openFinal(); return; }
    closeFinal();
    follow = false;
    const z = ORDER.indexOf(key);
    const zoneNodes = M.nodes.filter((n) => n.zone === z);
    if (!zoneNodes.length) return;
    const ys = zoneNodes.map((n) => n.point.y);
    const top = Math.min(...ys);
    const bottom = Math.max(...ys);
    const { cw, ch } = boxSize();
    const w = clamp((bottom - top + 240) * (cw / ch), closeW(), overviewCam().w);
    flyTo({ x: CX, y: (top + bottom) / 2, w }, 1100);
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
      const rect = scene.getBoundingClientRect();
      particles.burst(rect.width / 2, rect.height / 2 - 60, 120);
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

  function announce() {
    const gained = M.nodes.filter((n) => fresh.has(n.stage.id));
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

  // ---------- The opening shot ----------
  // The whole mountain first (start, summit, where you are), the road draws itself up the slope, the
  // camera comes down to the car, then the car climbs whatever was solved since the last visit.
  async function intro() {
    if (!M) return;
    const target = parking((id) => starsNow[id]);
    const from = before ? parking(starsBefore) : 0;
    const start = Math.min(from, target);
    placeCar(start);
    railCar(start);
    hud.alt.textContent = Math.round(M.altAt(M.carState.y)).toLocaleString("ru-RU");

    if (reduced) {
      placeCar(target);
      railCar(target);
      Object.assign(cam, camAt(target));
      applyCam();
      idle(true);
      youAreHere(true);
      return;
    }

    Object.assign(cam, overviewCam());
    applyCam();
    const drawMs = 1700;
    M.mask.animate([{ strokeDashoffset: M.total }, { strokeDashoffset: 0 }], { duration: drawMs, easing: "cubic-bezier(.65,0,.35,1)" });
    M.nodes.forEach((n) => {
      const delay = (n.at / M.total) * drawMs * 0.92;
      n.g.animate([{ opacity: 0, transform: `translate(${f1(n.point.x)}px, ${f1(n.point.y + 10)}px) scale(0.4)` }, { opacity: 1, transform: `translate(${f1(n.point.x)}px, ${f1(n.point.y)}px) scale(1)` }], { duration: 460, delay, easing: "cubic-bezier(.34,1.56,.64,1)", fill: "backwards" });
    });
    M.summit.animate([{ opacity: 0, transform: `translate(${M.geo.summit.x}px, ${M.geo.summit.y + 16}px)` }, { opacity: 1, transform: `translate(${M.geo.summit.x}px, ${M.geo.summit.y}px)` }], { duration: 600, delay: drawMs * 0.9, easing: "cubic-bezier(.22,1,.36,1)", fill: "backwards" });
    M.car.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400, delay: 200, fill: "backwards" });
    await wait(drawMs + 700);
    if (!alive()) return;
    if (camToken === 0) await flyTo(camAt(start), 1700);
    if (target > start + 1) {
      follow = camToken <= 1;
      await drive(start, target);
      follow = false;
    }
    idle(true);
    youAreHere(true);
    announce();
  }

  async function ceremonies() {
    for (const key of seasonsJustDone.slice(-1)) {
      await wait(400);
      const s = byKey[key];
      const next = seasons[ORDER.indexOf(key) + 1];
      scene.dataset.season = key;
      await ceremony({
        kicker: `${T.season_label} 0${ORDER.indexOf(key) + 1}`,
        title: `${s.title} ${T.season_done}`,
        stars: `${s.stars}/${s.max_stars}`,
        sub: next ? `${T.season_next}: ${next.title}` : T.final_motto,
        button: T.continue,
        icon: SEASON_ICONS[key],
      });
      hudKey = null;
      onCamera();
    }
    if (certifiedJustNow) {
      await openFinal();
      await ceremony({ kicker: T.finish, title: T.certified, sub: T.certified_sub, button: T.see_cert, icon: "ti-certificate" });
    }
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
    tab.addEventListener("click", () => showZone(tab.dataset.season));
    tab.addEventListener("keydown", (event) => {
      const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      event.preventDefault();
      const next = tabs[(i + step + tabs.length) % tabs.length];
      next.focus();
      showZone(next.dataset.season);
    });
  });
  root.querySelectorAll("[data-jr-go]").forEach((button) => button.addEventListener("click", () => {
    scene.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });
    showZone(button.dataset.jrGo);
  }));
  root.querySelectorAll("[data-jr-print]").forEach((button) => button.addEventListener("click", () => window.print()));
  scene.querySelectorAll("[data-jr-view]").forEach((button) => button.addEventListener("click", () => {
    if (!M) return;
    closePop();
    closeFinal();
    follow = false;
    if (button.dataset.jrView === "all") flyTo(isOverview() ? camAt(M.carAt) : overviewCam(), 1300);
    else flyTo(camAt(M.carAt), 1000);
  }));

  if ("ResizeObserver" in window) {
    let timer = null;
    new ResizeObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (!alive()) return;
        particles.resize();
        applyCam();
      }, 120);
    }).observe(mapBox);
  }

  // ---------- Result of the bilet just finished ----------
  // The result sheet opens over the road (kept visible behind it); the ceremonies play once it is closed.
  async function showResult(id) {
    try {
      const response = await fetch(D.result_url.replace(/0\/$/, `${id}/`), { credentials: "same-origin" });
      if (!response.ok) return false;
      const overlay = document.createElement("div");
      overlay.className = "rw-overlay";
      overlay.innerHTML = `<section class="rw-sheet" role="dialog" aria-modal="true">${await response.text()}</section>`;
      document.body.appendChild(overlay);
      return new Promise((resolve) => {
        const close = () => {
          document.removeEventListener("keydown", onEscape);
          overlay.classList.add("is-leaving");
          setTimeout(() => { overlay.remove(); resolve(true); }, reduced ? 0 : 250);
        };
        const onEscape = (event) => { if (event.key === "Escape") close(); };
        document.addEventListener("keydown", onEscape);
        overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });
        overlay.querySelectorAll("[data-rw-close]").forEach((button) => button.addEventListener("click", close));
      });
    } catch (e) { return false; }
  }

  async function start() {
    render();
    buildRail();
    if (!M) return;
    Object.assign(cam, overviewCam());
    applyCam();
    const id = new URLSearchParams(location.search).get("result");
    if (!/^\d+$/.test(id || "")) {
      await intro();
    } else {
      history.replaceState(null, "", location.pathname);
      // The result shows as soon as it loads; the climb plays behind it.
      await Promise.all([intro(), showResult(id)]);
    }
    if (alive()) ceremonies();
  }

  hero();
  start();
})();
