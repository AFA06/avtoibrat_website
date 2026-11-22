/* Real exam result intro on the bottom road. The barrier / finish line moves exactly with the road, so the
   car stops at it: speed up, brake, hit (failed) — or speed over the finish line (passed). Then the card shows. */
(function () {
  "use strict";
  const script = document.currentScript;
  const page = document.querySelector(".result-page--real");
  const road = page && page.querySelector(".result-road");
  const car = road && road.querySelector(".result-road__car");
  const announce = () => document.dispatchEvent(new Event("rx:reveal"));   // starts the score gauge
  if (!road || !car) { announce(); return; }
  const passed = script.dataset.passed === "1";
  const key = "ai.crash." + script.dataset.id;
  let seen = null;
  try { seen = localStorage.getItem(key); } catch (e) { /* storage blocked: just play */ }
  if (seen || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { announce(); return; }
  try { localStorage.setItem(key, "1"); } catch (e) { /* ignore */ }

  const ROAD_SPEED = 78 / 650;               // px per ms of the road lines at playbackRate 1
  const el = (cls, html) => { const n = document.createElement("div"); n.className = cls; if (html) n.innerHTML = html; return n; };
  const mark = passed ? el("rx-finish") : el("rx-barrier",
    '<svg viewBox="0 0 40 50"><rect x="5" y="20" width="5" height="30" fill="#94a3b8"/><rect x="30" y="20" width="5" height="30" fill="#94a3b8"/>' +
    '<rect x="0" y="8" width="40" height="16" rx="2" fill="#fff"/><path d="M4 8h8L2 24H0v-8zM20 8h8L16 24H8zM36 8h4v4L28 24h-8z" fill="#ef4444"/></svg>');
  const fx = el("rx-fx", '<i class="rx-smoke"></i><i class="rx-smoke"></i><i class="rx-smoke"></i><i class="rx-spark"></i><i class="rx-spark"></i><i class="rx-spark"></i><i class="rx-spark"></i>');
  const skid = el("rx-skid");
  road.append(skid, mark, fx);
  page.classList.add("rx-pending", passed ? "rx-pass" : "rx-fail");

  // Only the road's own animations (lines, wheels, bob) follow the speed.
  const moving = () => road.getAnimations({ subtree: true }).filter((a) => String(a.animationName || "").startsWith("result-"));
  const setRate = (r) => moving().forEach((a) => { a.playbackRate = Math.max(r, 0.0001); });

  // Speed profile (rate over time) and where the mark has to end up.
  const RAMP = passed ? 1100 : 700, BRAKE = passed ? 0 : 1400, TOP = passed ? 3 : 4;
  const rateAt = (t) => t < RAMP ? 1 + (TOP - 1) * t / RAMP : passed ? TOP : Math.max(0, TOP * (1 - (t - RAMP) / BRAKE));
  const total = RAMP + BRAKE;
  let distance = 0;                           // road travelled until the impact / the finish line
  for (let t = 0; t < total; t += 5) distance += rateAt(t) * ROAD_SPEED * 5;

  const front = () => { const b = car.getBoundingClientRect(); return b.right - 14 - road.getBoundingClientRect().left; };
  let x = front() + distance;                 // the mark's left edge, in road pixels
  const place = () => { mark.style.transform = `translateX(${x}px)`; };
  place();

  let start = null, last = null, stage = "drive", done = false;
  function frame(now) {
    if (done) return;
    if (start === null) { start = last = now; }
    const t = now - start, dt = now - last; last = now;
    let rate;
    if (stage === "drive") {
      rate = rateAt(Math.min(t, total));
      if (!passed && t > RAMP) road.classList.add("rx-braking");
      if (t >= total) { stage = passed ? "cross" : "hit"; impact(); }
    } else if (stage === "hit") {
      rate = 0;
    } else if (stage === "resume") {
      rate = Math.min(1, (now - resumeAt) / 1400);
    } else {                                   // passed: keep the top speed a moment, then settle
      rate = Math.max(1, TOP - (t - total) / 500);
    }
    setRate(rate);
    x -= rate * ROAD_SPEED * dt;
    place();
    if (x < -120 && (stage === "resume" || stage === "cross") && rate === 1) return cleanup();
    requestAnimationFrame(frame);
  }

  let resumeAt = 0;
  function impact() {
    if (passed) { setTimeout(reveal, 300); return; }
    road.classList.remove("rx-braking");
    road.classList.add("rx-hit");
    setTimeout(reveal, 900);
    setTimeout(() => { stage = "resume"; resumeAt = performance.now(); road.classList.add("rx-resume"); }, 2600);
  }
  function reveal() {
    if (!page.classList.contains("rx-pending")) return;
    announce();
    page.classList.remove("rx-pending");
    page.classList.add("rx-revealed");
  }
  function cleanup() {
    done = true;
    setRate(1);
    [mark, fx, skid].forEach((n) => n.remove());
    road.classList.remove("rx-braking", "rx-hit", "rx-resume");
    page.classList.remove("rx-pass", "rx-fail");
    document.removeEventListener("keydown", onKey);
  }
  function skip() { reveal(); cleanup(); }
  function onKey(e) { if (e.key === "Escape") skip(); }
  document.addEventListener("keydown", onKey);
  page.addEventListener("click", () => { if (page.classList.contains("rx-pending")) skip(); });
  requestAnimationFrame(frame);
})();
