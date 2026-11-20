// Reuse the story renderer and car. The native dialog owns focus and Escape.
import {Vector3, MathUtils} from 'three';

export function makePlayground(hero, layer, render, resize, signal) {
  const dialog = hero.querySelector('.drive-game');
  const launch = hero.querySelector('.game-launch');
  const originalSlot = layer.nextSibling;
  const held = new Set();
  const bindings = {KeyW:'forward', ArrowUp:'forward', KeyS:'back', ArrowDown:'back',
    KeyA:'left', ArrowLeft:'left', KeyD:'right', ArrowRight:'right'};
  const car = {position:new Vector3(), yaw:0, travel:0, steer:0};
  let speed = 0, last = 0, raf = 0, dirty = false;

  function reset() {
    car.position.set(127,0,-61);
    car.yaw = Math.PI / 2;
    car.steer = car.travel = speed = 0;
    held.clear();
    render(car);
  }
  function tick(time) {
    if (!dialog.open) return;
    const dt = Math.min(.06, (time-last)/1000);
    last = time;
    const drive = Number(held.has('forward')) - Number(held.has('back'));
    speed = drive ? MathUtils.clamp(speed + drive*8*dt,-4,9) : MathUtils.damp(speed,0,2,dt);
    const oldSteer = car.steer;
    const turn = Number(held.has('left')) - Number(held.has('right'));
    car.steer = MathUtils.damp(car.steer,turn*.54,8,dt);
    const distance = speed*dt;
    const yaw = car.yaw + distance*Math.tan(car.steer)/2.86;
    const x = car.position.x + Math.sin(yaw)*distance;
    const z = car.position.z + Math.cos(yaw)*distance;
    const nearCone = Math.abs(z+53)<1.35 && x>=116.7 && x<=156.3 &&
      Math.hypot(x-(118+Math.round((x-118)/3.7)*3.7),z+53)<1.35;
    if (x<113 || x>160 || z< -67 || z> -42 || nearCone) speed=0;
    else {car.position.set(x,0,z);car.yaw=yaw;car.travel+=distance}
    if (dirty || Math.abs(distance)>.00001 || Math.abs(oldSteer-car.steer)>.0001) render(car);
    dirty=false;
    raf=requestAnimationFrame(tick);
  }
  launch.addEventListener('click',()=>{
    dialog.showModal();
    dialog.prepend(layer);
    document.documentElement.classList.add('yard-open');
    resize();reset();last=performance.now();raf=requestAnimationFrame(tick);
  },{signal});
  function restore() {
    if (layer.parentNode===hero) return;
    cancelAnimationFrame(raf);held.clear();
    hero.insertBefore(layer,originalSlot);
    document.documentElement.classList.remove('yard-open');
    resize();
  }
  function exit() { dialog.close();restore() }
  dialog.addEventListener('cancel',event=>{event.preventDefault();exit()},{signal});
  dialog.addEventListener('close',restore,{signal});
  dialog.querySelector('.yard-exit').addEventListener('click',exit,{signal});
  dialog.querySelector('.yard-reset').addEventListener('click',reset,{signal});
  for (const name of ['keydown','keyup']) dialog.addEventListener(name,e=>{
    const input=bindings[e.code];if(!input)return;
    e.preventDefault();if(name==='keydown')held.add(input);else held.delete(input);
  },{signal});
  for(const button of dialog.querySelectorAll('[data-drive]')){
    const key=button.dataset.drive;
    button.addEventListener('pointerdown',e=>{button.setPointerCapture(e.pointerId);held.add(key)},{signal});
    for(const event of ['pointerup','lostpointercapture','pointercancel'])button.addEventListener(event,()=>held.delete(key),{signal});
    button.addEventListener('click',e=>{
      if(e.detail!==0)return;
      held.add(key);setTimeout(()=>held.delete(key),350);
    },{signal});
  }
  window.addEventListener('blur',()=>held.clear(),{signal});
  return {invalidate(){dirty=true},get active(){return dialog.open},dispose(){if(dialog.open){dialog.close();restore()}}};
}
