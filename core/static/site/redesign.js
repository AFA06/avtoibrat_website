(function () {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Only hide sections once an observer exists; the full page works without JavaScript.
  if ('IntersectionObserver' in window && !reduced) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.remove('is-pending');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll('.sec__head, .experience-grid, .school-metrics, .skills-layout, .route, .cat, .platform__grid, .person, .review, .faq, .apply').forEach(function (el) {
      el.classList.add('reveal');
      if (el.getBoundingClientRect().top > window.innerHeight) el.classList.add('is-pending');
      observer.observe(el);
    });
  }
  var progress = document.querySelector('.reading-progress');
  var scheduled = false;
  function updateProgress() {
    var range = document.documentElement.scrollHeight - window.innerHeight;
    if (progress) progress.style.transform = 'scaleX(' + (range > 0 ? Math.min(1, window.scrollY / range) : 0) + ')';
    scheduled = false;
  }
  window.addEventListener('scroll', function () {
    if (!scheduled) { scheduled = true; window.requestAnimationFrame(updateProgress); }
  }, { passive: true });
  window.addEventListener('resize', updateProgress);
  updateProgress();
  var tabs = Array.from(document.querySelectorAll('[data-skill]'));
  function activate(tab) {
    tabs.forEach(function (other) {
      var selected = other === tab;
      other.setAttribute('aria-selected', String(selected));
      other.tabIndex = selected ? 0 : -1;
      document.getElementById(other.getAttribute('aria-controls')).hidden = !selected;
    });
    document.querySelector('.skill-map').setAttribute('data-mode', tab.dataset.skill);
  }
  tabs.forEach(function (tab, index) {
    tab.addEventListener('click', function () { activate(tab); });
    tab.addEventListener('keydown', function (event) {
      var next;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); activate(tabs[next]); tabs[next].focus(); }
    });
  });
  document.querySelectorAll('[data-answer]').forEach(function (button) {
    button.addEventListener('click', function () {
      var question = button.closest('.exam__q');
      question.querySelectorAll('[data-answer]').forEach(function (answer) {
        answer.classList.remove('is-right', 'is-wrong');
        answer.removeAttribute('aria-pressed');
      });
      var correct = button.dataset.answer === 'right';
      button.classList.add(correct ? 'is-right' : 'is-wrong');
      button.setAttribute('aria-pressed', 'true');
      var feedback = question.querySelector('.demo-feedback');
      feedback.textContent = correct ? feedback.dataset.correct : feedback.dataset.wrong;
    });
  });
})();
