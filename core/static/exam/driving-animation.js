(function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const XLINK_NS = "http://www.w3.org/1999/xlink";

  function svgElement(name, attributes) {
    const element = document.createElementNS(SVG_NS, name);
    Object.entries(attributes || {}).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }

  function localized(values, language) {
    return values[language] || values.uz || Object.values(values)[0] || "";
  }

  function createCar(vehicle, language) {
    const group = svgElement("g", {
      class: "drive-car",
      role: "img",
      "aria-label": localized(vehicle.labels, language),
    });
    const shadow = svgElement("ellipse", { cx: "2", cy: "3", rx: "37", ry: "18", class: "drive-car__shadow" });
    const wheels = [
      [-20, -19], [17, -19], [-20, 15], [17, 15],
    ].map(([x, y]) => svgElement("rect", { x, y, width: "12", height: "5", rx: "2", class: "drive-car__wheel" }));
    const body = svgElement("path", {
      d: "M-32-14 Q-26-18-15-18 H16 Q27-18 34-9 L37 0 34 9 Q27 18 16 18 H-15 Q-26 18-32 14 L-36 7 V-7Z",
      fill: vehicle.color,
      class: "drive-car__body",
    });
    const cabin = svgElement("path", {
      d: "M-12-13 H13 Q21-13 26-7 L28 0 26 7 Q21 13 13 13 H-12 L-18 7 V-7Z",
      class: "drive-car__cabin",
    });
    const divider = svgElement("path", { d: "M7-13V13M-13-12L-18-7M-13 12L-18 7", class: "drive-car__glassline" });
    const headlights = svgElement("path", { d: "M31-10L35-6M31 10L35 6", class: "drive-car__headlights" });
    const taillights = svgElement("path", { d: "M-31-11L-34-7M-31 11L-34 7", class: "drive-car__taillights" });
    group.append(shadow, ...wheels, body, cabin, divider, headlights, taillights);
    return group;
  }

  class DrivingAnimationController {
    constructor(root, scenario, language, strings) {
      this.root = root;
      this.scenario = scenario;
      this.language = language;
      this.strings = strings;
      this.currentTime = 0;
      this.playing = false;
      this.speed = 1;
      this.frame = null;
      this.lastFrameTime = null;
      this.listeners = [];
      this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      this.build();
      this.renderAt(0);
      if (!this.reducedMotion) requestAnimationFrame(() => this.play());
    }

    build() {
      this.root.textContent = "";
      this.root.className = "drive-animation";
      this.root.classList.toggle("drive-animation--reduced", this.reducedMotion);

      const heading = document.createElement("div");
      heading.className = "drive-animation__heading";
      const title = document.createElement("strong");
      title.textContent = this.strings.title;
      const time = document.createElement("span");
      time.className = "drive-animation__time";
      time.textContent = `0:00 / ${this.formatTime(this.scenario.duration)}`;
      heading.append(title, time);
      this.timeLabel = time;

      const stage = document.createElement("div");
      stage.className = "drive-animation__stage";
      const scene = svgElement("svg", {
        viewBox: this.scenario.viewBox,
        preserveAspectRatio: "xMidYMid meet",
        class: "drive-animation__scene",
        "aria-hidden": "true",
      });
      const background = svgElement("image", { width: "945", height: "530", preserveAspectRatio: "xMidYMid slice" });
      background.setAttribute("href", this.scenario.background);
      background.setAttributeNS(XLINK_NS, "xlink:href", this.scenario.background);
      scene.appendChild(background);

      const routeLayer = svgElement("g", { class: "drive-routes" });
      const carLayer = svgElement("g", { class: "drive-cars" });
      scene.append(routeLayer, carLayer);
      stage.appendChild(scene);

      this.vehicles = this.scenario.vehicles.map((vehicle) => {
        const segments = vehicle.segments.map((segment) => {
          const path = svgElement("path", { d: segment.path, class: "drive-route", stroke: vehicle.color });
          routeLayer.appendChild(path);
          return { ...segment, path, length: path.getTotalLength() };
        });
        const car = createCar(vehicle, this.language);
        carLayer.appendChild(car);
        return { ...vehicle, segments, car };
      });

      const controls = document.createElement("div");
      controls.className = "drive-animation__controls";
      this.playButton = this.controlButton("▶", this.strings.play, () => this.play());
      this.pauseButton = this.controlButton("Ⅱ", this.strings.pause, () => this.pause());
      this.replayButton = this.controlButton("↻", this.strings.replay, () => this.replay());
      this.progress = document.createElement("progress");
      this.progress.className = "drive-animation__progress";
      this.progress.max = this.scenario.duration;
      this.progress.value = 0;
      this.progress.setAttribute("aria-label", this.strings.title);

      const speedLabel = document.createElement("label");
      speedLabel.className = "drive-animation__speed";
      const speedText = document.createElement("span");
      speedText.textContent = this.strings.speed;
      const speed = document.createElement("select");
      [0.5, 1, 1.5].forEach((value) => {
        const option = document.createElement("option");
        option.value = String(value);
        option.textContent = `${value}×`;
        option.selected = value === 1;
        speed.appendChild(option);
      });
      this.listen(speed, "change", () => { this.speed = Number(speed.value) || 1; });
      speedLabel.append(speedText, speed);
      controls.append(this.playButton, this.pauseButton, this.replayButton, this.progress, speedLabel);

      const details = document.createElement("div");
      details.className = "drive-animation__details";
      const explanation = document.createElement("p");
      explanation.className = "drive-animation__explanation";
      explanation.textContent = localized(this.scenario.explanations, this.language);
      const steps = document.createElement("ol");
      steps.className = "drive-animation__steps";
      this.stepItems = this.scenario.steps.map((step) => {
        const item = document.createElement("li");
        item.textContent = localized(step.labels, this.language);
        steps.appendChild(item);
        return item;
      });
      details.append(explanation, steps);

      if (this.reducedMotion) {
        const notice = document.createElement("p");
        notice.className = "drive-animation__notice";
        notice.textContent = this.strings.reducedMotion;
        details.prepend(notice);
        this.playButton.disabled = true;
        this.pauseButton.disabled = true;
        speed.disabled = true;
      }

      this.root.append(heading, stage, controls, details);
    }

    controlButton(icon, label, handler) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "drive-animation__button";
      button.setAttribute("aria-label", label);
      button.innerHTML = `<span aria-hidden="true">${icon}</span><span>${label}</span>`;
      this.listen(button, "click", handler);
      return button;
    }

    listen(element, event, handler) {
      element.addEventListener(event, handler);
      this.listeners.push(() => element.removeEventListener(event, handler));
    }

    play() {
      if (this.reducedMotion || this.playing) return;
      if (this.currentTime >= this.scenario.duration) this.renderAt(0);
      this.playing = true;
      this.lastFrameTime = performance.now();
      this.updateControls();
      this.frame = requestAnimationFrame((time) => this.tick(time));
    }

    pause() {
      if (!this.playing) return;
      this.playing = false;
      if (this.frame !== null) cancelAnimationFrame(this.frame);
      this.frame = null;
      this.lastFrameTime = null;
      this.updateControls();
    }

    replay() {
      if (this.reducedMotion) {
        this.renderAt(0);
        return;
      }
      this.pause();
      this.renderAt(0);
      this.play();
    }

    tick(frameTime) {
      if (!this.playing) return;
      const delta = Math.min(frameTime - this.lastFrameTime, 100) * this.speed;
      this.lastFrameTime = frameTime;
      this.renderAt(Math.min(this.currentTime + delta, this.scenario.duration));
      if (this.currentTime >= this.scenario.duration) {
        this.playing = false;
        this.frame = null;
        this.updateControls();
        return;
      }
      this.frame = requestAnimationFrame((time) => this.tick(time));
    }

    renderAt(time) {
      this.currentTime = time;
      this.vehicles.forEach((vehicle) => this.placeVehicle(vehicle, time));
      this.progress.value = time;
      this.timeLabel.textContent = `${this.formatTime(time)} / ${this.formatTime(this.scenario.duration)}`;
      this.stepItems.forEach((item, index) => {
        const step = this.scenario.steps[index];
        item.classList.toggle("is-active", time >= step.start && time < step.end);
        item.classList.toggle("is-complete", time >= step.end);
      });
      this.updateControls();
    }

    placeVehicle(vehicle, time) {
      let segment = vehicle.segments[0];
      let distance = 0;
      let waiting = time < segment.start;

      for (let index = 0; index < vehicle.segments.length; index += 1) {
        const candidate = vehicle.segments[index];
        const end = candidate.start + candidate.duration;
        if (time < candidate.start) {
          if (index > 0) {
            segment = vehicle.segments[index - 1];
            distance = segment.length;
            waiting = true;
          }
          break;
        }
        segment = candidate;
        if (time <= end) {
          distance = segment.length * ((time - segment.start) / segment.duration);
          waiting = false;
          break;
        }
        distance = segment.length;
        waiting = index < vehicle.segments.length - 1;
      }

      const point = segment.path.getPointAtLength(distance);
      const sampleDistance = Math.min(segment.length, distance + 2);
      const alternateDistance = Math.max(0, distance - 2);
      const tangent = segment.path.getPointAtLength(sampleDistance === distance ? alternateDistance : sampleDistance);
      const angle = Math.atan2(tangent.y - point.y, tangent.x - point.x) * 180 / Math.PI;
      vehicle.car.setAttribute("transform", `translate(${point.x} ${point.y}) rotate(${angle})`);
      vehicle.car.classList.toggle("is-waiting", waiting);
    }

    updateControls() {
      if (!this.playButton) return;
      this.playButton.disabled = this.reducedMotion || this.playing;
      this.pauseButton.disabled = this.reducedMotion || !this.playing;
    }

    formatTime(milliseconds) {
      const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
      return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    }

    destroy() {
      this.pause();
      this.listeners.forEach((remove) => remove());
      this.listeners = [];
      this.root.textContent = "";
    }
  }

  window.DrivingAnimation = {
    mount(root, scenario, language, strings) {
      return new DrivingAnimationController(root, scenario, language, strings);
    },
  };
})();
