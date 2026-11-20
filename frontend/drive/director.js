export function makeDirector(hero,draw,signal){
 const hud=hero.querySelector('.drive-hud'), layout=hero.querySelector('.pass-layout'),copy=hud.querySelector('.scene-copy');
 const cues=[...hud.querySelectorAll('[data-seek]')],panels=[...copy.querySelectorAll('[data-chapter]')];
 const links=hud.querySelector('.drive-links'),next=hud.querySelector('.drive-next'),driveLabel=next.textContent;
 const state={progress:0,opening:0};let previous=-1;
 function frame(){
  const p=state.progress;
  const chapter=p<.085?0:p<.21?1:p<.36?2:p<.55?3:p<.83?4:5;
  if(chapter!==previous){
   previous=chapter;layout.hidden=chapter!==0;copy.hidden=chapter===0;links.hidden=chapter===0;
   next.textContent=chapter===5?next.dataset.finish:driveLabel;
   panels.forEach(el=>el.hidden=Number(el.dataset.chapter)!==chapter);
   cues.forEach((el,i)=>{if(i===chapter)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current')});
   copy.querySelector('.scene-count').textContent='0'+(chapter+1)+' / 06';
  }
  draw(p,state.opening);
 }
 const timeline=gsap.timeline({scrollTrigger:{id:'drive',trigger:hero,start:()=> 'top '+document.querySelector('.top').offsetHeight+'px',end:()=>'+='+Math.max(1700,innerHeight*3.3),pin:true,scrub:.22,invalidateOnRefresh:true}});
 timeline.to(state,{progress:1,ease:'none',onUpdate:frame});
 const intro=gsap.to(state,{opening:1,duration:.85,ease:'power2.out',onUpdate:frame});
 function seek(p){
  intro.progress(1);const t=timeline.scrollTrigger;
  window.scrollTo({top:t.start+p*(t.end-t.start),behavior:'smooth'});
 }
 cues.forEach(el=>el.addEventListener('click',()=>seek(Number(el.dataset.seek)),{signal}));
 hud.querySelector('.drive-next').addEventListener('click',()=>{
  if(previous===5){document.getElementById('courses')?.scrollIntoView();return}
  seek(Number(cues[previous+1].dataset.seek));
 },{signal});
 hud.hidden=false;frame();ScrollTrigger.refresh();
 return {state,frame,dispose(){intro.kill();timeline.scrollTrigger.kill();timeline.kill();hud.hidden=true;layout.hidden=false}};
}
