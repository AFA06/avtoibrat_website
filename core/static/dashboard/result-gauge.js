(() => {
  const svgNS = "http://www.w3.org/2000/svg";
  const ticks = document.querySelector(".result-gauge__ticks");
  const labels = document.querySelector(".result-gauge__labels");
  if (!ticks || !labels) return;

  const centerX = 110;
  const centerY = 112;
  const pointAt = (radius, angle) => ({
    x: centerX + radius * Math.cos(angle),
    y: centerY - radius * Math.sin(angle),
  });

  for (let step = 0; step <= 40; step += 1) {
    const angle = Math.PI - (step / 40) * Math.PI;
    const major = step % 8 === 0;
    const outer = pointAt(88, angle);
    const inner = pointAt(major ? 75 : 82, angle);
    const line = document.createElementNS(svgNS, "line");
    line.setAttribute("x1", inner.x);
    line.setAttribute("y1", inner.y);
    line.setAttribute("x2", outer.x);
    line.setAttribute("y2", outer.y);
    line.setAttribute("class", major ? "is-major" : "");
    ticks.appendChild(line);
  }

  for (let value = 0; value <= 100; value += 20) {
    const angle = Math.PI - (value / 100) * Math.PI;
    const point = pointAt(104, angle);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", point.x);
    label.setAttribute("y", point.y);
    label.textContent = value;
    labels.appendChild(label);
  }

  const page = document.querySelector(".result-page--real");
  if (!page || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const gauge = page.querySelector(".result-gauge");
  const needle = gauge.querySelector(".result-gauge__needle");
  const number = gauge.querySelector(".result-gauge__number");
  const caption = gauge.querySelector(".result-gauge__label");
  const score = Number(gauge.getAttribute("aria-valuenow"));
  const resultCaption = caption.textContent;
  const sweepDuration = 650;
  const countDuration = 1100;
  const start = performance.now();

  function pointNeedle(percent) {
    needle.setAttribute("transform", `rotate(${percent * 1.8} ${centerX} ${centerY})`);
  }

  function animate(now) {
    const elapsed = Math.max(0, now - start);
    if (elapsed < sweepDuration) {
      // Sweep the dial before counting so a zero score still has a visible animation.
      pointNeedle(Math.sin(Math.PI * elapsed / sweepDuration) * 100);
    } else {
      const progress = Math.min(1, (elapsed - sweepDuration) / countDuration);
      const displayed = score * (1 - (1 - progress) ** 3);
      pointNeedle(displayed);
      number.textContent = Math.round(displayed);
      if (progress === 1) {
        caption.textContent = resultCaption;
        gauge.removeAttribute("aria-busy");
        page.classList.replace("result-page--counting", "result-page--revealed");
        return;
      }
    }
    requestAnimationFrame(animate);
  }

  page.classList.add("result-page--counting");
  gauge.setAttribute("aria-busy", "true");
  caption.textContent = caption.dataset.countingLabel;
  number.textContent = "0";
  pointNeedle(0);
  // A real exam may play the road intro (real-crash.js): the needle follows the car's speed, then the crash
  // (or finish) drops it onto the real score. Without the intro the usual sweep-and-count runs.
  if (page.dataset.intro) {
    let current = 0;
    let settled = false;
    window.resultGauge = {
      speed(percent) {
        if (settled) return;
        current = Math.max(0, Math.min(100, percent));
        pointNeedle(current);
        number.textContent = Math.round(current);
      },
      settle(crashed) {
        if (settled) return;
        settled = true;
        const from = current;
        const begin = performance.now();
        const duration = crashed ? 1300 : 900;
        (function drop(now) {
          const p = Math.min(1, (now - begin) / duration);
          // A crash makes the needle shudder as it falls; a finish eases in smoothly.
          const shake = crashed ? Math.sin(p * Math.PI * 7) * 9 * (1 - p) : 0;
          const value = from + (score - from) * (1 - (1 - p) ** 3) + shake;
          pointNeedle(Math.max(0, Math.min(100, value)));
          number.textContent = Math.round(Math.max(0, from + (score - from) * (1 - (1 - p) ** 3)));
          if (p < 1) { requestAnimationFrame(drop); return; }
          pointNeedle(score);
          number.textContent = score;
          caption.textContent = resultCaption;
          gauge.removeAttribute("aria-busy");
          page.classList.replace("result-page--counting", "result-page--revealed");
        })(begin);
      },
    };
  } else {
    requestAnimationFrame(animate);
  }
})();
