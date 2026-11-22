/* Real exam result intro: plays once per exam, then fades away to the result underneath. */
(function () {
  "use strict";
  const box = document.getElementById("rx");
  if (!box) return;
  const key = "ai.crash." + box.dataset.id;
  let seen = null;
  try { seen = localStorage.getItem(key); } catch (e) { /* storage blocked: just play */ }
  if (seen || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { box.remove(); return; }
  try { localStorage.setItem(key, "1"); } catch (e) { /* ignore */ }

  box.hidden = false;
  document.documentElement.classList.add("rx-lock");
  requestAnimationFrame(() => box.classList.add("is-playing"));

  let done = false;
  function finish() {
    if (done) return;
    done = true;
    box.classList.add("is-leaving");
    document.documentElement.classList.remove("rx-lock");
    setTimeout(() => box.remove(), 450);
    document.removeEventListener("keydown", onKey);
  }
  function onKey(e) { if (e.key === "Escape" || e.key === "Enter" || e.key === " ") finish(); }
  box.addEventListener("click", finish);
  document.addEventListener("keydown", onKey);
  setTimeout(finish, box.classList.contains("rx--fail") ? 4200 : 3400);
})();
