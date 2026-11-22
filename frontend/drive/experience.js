import * as THREE from 'three';
import {makeWorld} from './world.js';
import {makeDirector} from './director.js';
import {makePlayground} from './playground.js';

const hero = document.querySelector('.pass');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let generation = 0, cleanup = () => {};

async function start() {
  const token = ++generation;
  cleanup();
  if (!hero || !window.ScrollTrigger || reduced.matches || navigator.connection?.saveData) return;

  const layer = hero.querySelector('.drive-view');
  const canvas = document.createElement('canvas');
  const events = new AbortController();
  let renderer, world, director, playground, observer, last, blinkTimer;
  let ready = false, disposed = false;
  function dispose() {
    if (disposed) return;
    disposed = true;
    ready = false;
    events.abort();
    observer?.disconnect();
    clearInterval(blinkTimer);
    playground?.dispose();
    director?.dispose();
    world?.dispose();
    renderer?.dispose();
    canvas.remove();
    hero.classList.remove('driving');
    delete hero.driveFrame;
  }
  cleanup = dispose;
  try {
    const context = canvas.getContext('webgl2', {antialias:true, powerPreference:'high-performance'});
    if (!context) return;
    renderer = new THREE.WebGLRenderer({canvas,context});
    const tier = innerWidth<=720 ? 'mobile' : innerWidth<1200 ? 'standard' : 'large';
    let ratio = Math.min(devicePixelRatio, {mobile:1, standard:1.25, large:1.6}[tier]);
    renderer.setPixelRatio(ratio);
    renderer.shadowMap.enabled = tier !== 'mobile';
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.02;
    world = await makeWorld(renderer, layer.dataset.car);
    if (token !== generation) {world.dispose();return}
    layer.append(canvas);
    hero.classList.add('driving');
    let slow = 0;
    function draw(p, opening) {
      if (playground?.active) return;
      const now = performance.now();
      last = {...world.pose(p,opening),progress:p};
      if (performance.now()-now>55) slow++;
      else slow = Math.max(0,slow-1);
      if (slow>6 && ratio>.76) {
        ratio = Math.max(.75,ratio*.85);
        renderer.setPixelRatio(ratio);
        slow = 0;
      }
    }
    function resize() {
      if (disposed) return;
      const w = layer.clientWidth, h = layer.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w,h,false);
      const camera = world.camera;
      camera.aspect = w/h;
      const portrait = w<h;
      camera.fov = portrait ? THREE.MathUtils.clamp(2*Math.atan(Math.tan(.325)*h/w)*180/Math.PI,54,76) : 42;
      camera.setViewOffset(w,h,!portrait && w>700 && !playground?.active ? -w*.18 : 0,
        portrait && !playground?.active ? -h*.10 : 0,w,h);
      camera.updateProjectionMatrix();
      if (playground?.active) playground.invalidate();
      else if (ready) director.frame();
    }
    resize();
    director = makeDirector(hero,draw,events.signal);
    playground = makePlayground(hero,layer,car=>{
      last={...world.pose(1,1,car),progress:director.state.progress};
    },resize,events.signal);
    ready = true;
    // Only redraw a stationary story frame while a turn signal is active.
    blinkTimer=setInterval(()=>{if(last?.indicator && !document.hidden && hero.getBoundingClientRect().bottom>0 && hero.getBoundingClientRect().top<innerHeight)director.frame()},120);
    hero.driveFrame = () => ({...last});
    observer = new ResizeObserver(resize);
    observer.observe(layer);
    canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();dispose()},{signal:events.signal});
  } catch (error) {
    if (token===generation) {dispose();console.warn('3D preview unavailable:',error.message)}
  }
}
if (document.readyState==='complete') start();
else window.addEventListener('DOMContentLoaded',start,{once:true});
reduced.addEventListener('change',start);
window.addEventListener('pagehide',()=>{generation++;cleanup()});
window.addEventListener('pageshow',e=>{if(e.persisted)start()});
