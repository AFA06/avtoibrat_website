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
})();
