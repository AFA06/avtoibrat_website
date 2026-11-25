(() => {
  const all = (selector, root = document) => [...root.querySelectorAll(selector)];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const quiz = document.querySelector('.quiz');
  const answers = all('[data-sign]', quiz);
  const sequence = ['2.1', '2.4', '2.2'];
  const feedback = quiz.querySelector('.verdict');
  const next = quiz.querySelector('.advance');
  let index = 0;
  const correct = () => answers.find(button => button.dataset.sign === sequence[index]);
  function showQuestion() {
    const sign = correct();
    const image = quiz.querySelector('.quiz-prompt img');
    image.src = sign.dataset.src;
    image.alt = sign.dataset.shape;
    quiz.querySelector('output').textContent = '0' + (index + 1) + ' / 03';
    quiz.querySelector('progress').value = index;
    answers.forEach(button => { button.disabled = false; button.classList.remove('correct','error'); });
    feedback.textContent = '';
    next.disabled = true;
    next.textContent = index === sequence.length - 1 ? quiz.dataset.retry : quiz.dataset.next;
  }
  answers.forEach(button => button.addEventListener('click', () => {
    const answer = correct();
    answers.forEach(item => { item.disabled = true; });
    answer.classList.add('correct');
    if (button !== answer) button.classList.add('error');
    feedback.textContent = button === answer ? feedback.dataset.right : feedback.dataset.wrong + ' ' + answer.lastChild.textContent;
    quiz.querySelector('progress').value = index + 1;
    next.textContent = index === sequence.length - 1 ? quiz.dataset.retry : quiz.dataset.next;
    next.disabled = false;
    next.focus({preventScroll:true});
  }));
  next.addEventListener('click', () => {
    index = (index + 1) % sequence.length;
    showQuestion();
    answers[0].focus({preventScroll:true});
  });
  if (!window.gsap || !window.ScrollTrigger) return;
  gsap.registerPlugin(ScrollTrigger);
  const motion = gsap.matchMedia();
  motion.add('(prefers-reduced-motion: no-preference)', () => {
    const intro = gsap.timeline({defaults:{ease:'power3.out'}});
    intro.from('.top__inner',{y:-8,duration:.38})
      .from('.pass-photo',{scale:1.055,duration:1.25},0)
      .from('.pass h1 b,.pass h1 em',{yPercent:110,stagger:.09,duration:.72},.06)
      .from('.pass-actions',{y:10,opacity:.55,duration:.5},.32)
      .from('.pass-base',{clipPath:'inset(0 85% 0 0)',duration:.75},.24);
    gsap.from('.lesson-film img',{scale:1.075,scrollTrigger:{trigger:'.lesson-film',start:'top bottom',end:'bottom center',scrub:true}});
    gsap.from('.foot__base',{scaleX:.92,transformOrigin:'left',scrollTrigger:{trigger:'.foot',start:'top bottom',end:'bottom bottom',scrub:true}});
  });
  document.fonts.ready.then(()=>ScrollTrigger.refresh());
})();
