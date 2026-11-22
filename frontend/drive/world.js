import * as T from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {buildRoad,path,length,frame,at} from './road.js';
import {districts,carShadow} from './districts.js';
export async function makeWorld(renderer,url){
 const scene=new T.Scene(),camera=new T.PerspectiveCamera(42,1,.55,290);
 scene.background=new T.Color(0xdcd8cd);scene.fog=new T.FogExp2(0xdcd8cd,.014);
 const env=new RoomEnvironment(),pm=new T.PMREMGenerator(renderer),reflection=pm.fromScene(env,.025);scene.environment=reflection.texture;env.dispose();pm.dispose();
 const sky=new T.HemisphereLight(0xffe8cc,0x94a0aa,1.75);scene.add(sky);
 const sun=new T.DirectionalLight(0xffdfbc,2.9);sun.position.set(20,34,15);scene.add(sun,sun.target);
 const ground=new T.Mesh(new T.PlaneGeometry(1000,1000),new T.MeshStandardMaterial({color:0xc5b8a1}));ground.rotation.x=-Math.PI/2;ground.position.y=-.16;scene.add(ground);buildRoad(scene);
 const car=(await new GLTFLoader().loadAsync(url)).scene;scene.add(car);
 const wheels=[],front=[];car.traverse(o=>{if(o.name.startsWith('Wheel_'))wheels.push(o);if(o.name.startsWith('Knuckle_F'))front.push(o)});

 const district=districts(scene);
 carShadow(car);
 car.traverse(o=>{if(o.isMesh && !o.material.transparent)o.castShadow=true});
 ground.receiveShadow=true;sun.castShadow=true;sun.shadow.mapSize.set(512,512);
 Object.assign(sun.shadow.camera,{left:-8,right:8,top:8,bottom:-8,near:1,far:75});sun.shadow.normalBias=.025;
 const dome=new T.Mesh(new T.SphereGeometry(260,24,12),new T.ShaderMaterial({
   side:T.BackSide,depthWrite:false,
   uniforms:{dusk:{value:0}},
   vertexShader:'varying vec3 v;void main(){v=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
   fragmentShader:`uniform float dusk;varying vec3 v;void main(){vec3 d=normalize(v);float k=smoothstep(-.03,.76,d.y);vec3 base=mix(mix(vec3(.92,.71,.51),vec3(.69,.82,.84),dusk),mix(vec3(.24,.42,.52),vec3(.22,.46,.66),dusk),k);float sun=pow(max(dot(d,normalize(vec3(-.6,.23,-.7))),0.),150.);gl_FragColor=vec4(base+sun*vec3(.9,.62,.35),1.);
   #include <colorspace_fragment>
   }`
 }));scene.add(dome);
 const dist=[0];let prev=at(0,2.5);
 for(let i=1;i<=500;i++){const pt=at(i/500,2.5);dist.push(dist[i-1]+prev.distanceTo(pt));prev=pt}
 function distance(u){const ix=Math.min(499,Math.floor(u*500));return T.MathUtils.lerp(dist[ix],dist[ix+1],u*500-ix)}
 const smooth=T.MathUtils.smoothstep, mix=T.MathUtils.lerp;
 function route(p){
   if(p<.40){const x=p/.40;return .075+.181*(1-Math.pow(1-x,1.35))}
   if(p<.48)return .256;
   const x=(p-.48)/.52;return .256+.670*(x*x*(3-2*x));
 }
 const cool=new T.Color(0xb7d1d5),warm=new T.Color(0xead3b8),baseLight=new T.Color(0xffd4a4),day=new T.Color(0xfff3da);
 const scratch=new T.Vector3(),look=new T.Vector3();
 const shell=car.getObjectByName('Coachwork');
 const lamps=shell.children.filter(o=>o.name==='Headlamp');
 const indicators=shell.children.filter(o=>o.name.startsWith('Indicator_'));
 const brakes=shell.children.filter(o=>o.name==='Brake');
 let indicator=null,blink=false;
 function renderCar(position,yaw,travel,steer){
  car.position.copy(position);car.position.y=.030;car.rotation.y=yaw;
  wheels.forEach(o=>o.rotation.x=travel/.30);front.forEach(o=>o.rotation.y=steer);
  sun.target.position.copy(car.position);sun.position.copy(car.position).add(scratch.set(-16,24,9));
 }
 function pose(p,opening=1,manual=null){
  const u=route(p),f=frame(u),next=path.getTangentAt(Math.min(1,u+.004));
  const turn=Math.atan2(f.t.z*next.x-f.t.x*next.z,f.t.dot(next));
  const steer=Math.atan(2.86*turn/(length*.004));
  renderCar(manual?manual.position:at(u,2.5),manual?manual.yaw:Math.atan2(f.t.x,f.t.z),manual?manual.travel:distance(u)-distance(.075),manual?manual.steer:steer);
  const steering=manual?manual.steer:steer;
  indicator=Math.abs(steering)>.018?(steering>0?'L':'R'):null;
  blink=indicator!==null && Math.floor(performance.now()/420)%2===0;
  indicators.forEach(o=>o.material.emissiveIntensity=blink && o.name==='Indicator_'+indicator?3:0);
  const braking=manual?manual.braking:p>.37&&p<.48;
  brakes.forEach(o=>o.material.emissiveIntensity=braking?2.4:.18);
  const change=smooth(p,.52,.80);dome.material.uniforms.dusk.value=change;scene.fog.color.copy(warm).lerp(cool,change);scene.fog.density=mix(.012,.0075,change);
  sun.color.copy(baseLight).lerp(day,change);sun.intensity=1.75+.65*opening;sky.intensity=1.05+.32*opening;
  lamps.forEach(o=>o.material.emissiveIntensity=.20+1.25*opening);
  const state=district.update(p,opening);
  // Camera angles are relative to the tangent, so tracking continues through the turn.
  const angle=5.55-2.19*smooth(p,.02,.24)+.68*smooth(p,.30,.44)-1.18*smooth(p,.49,.65)-2.26*smooth(p,.71,.94);
  const orbit=8.5+3.1*(1-opening)+1.6*smooth(p,.3,.43)+3.5*Math.sin(Math.PI*smooth(p,.59,.89));
  const height=2.00+1.2*(1-opening)+1.0*smooth(p,.14,.32)+4.8*Math.sin(Math.PI*smooth(p,.58,.91));
  if(manual){
   camera.position.copy(car.position).add(scratch.set(-Math.sin(manual.yaw)*7,4.6,-Math.cos(manual.yaw)*7));
  }else{
   camera.position.copy(car.position).addScaledVector(f.t,Math.cos(angle)*orbit).addScaledVector(f.side,Math.sin(angle)*orbit);
   camera.position.y=height;
  }
  look.copy(car.position);look.addScaledVector(f.t,manual?0:(camera.aspect<1?.65:1.8)*(smooth(p,.29,.40)-smooth(p,.48,.57)));look.y+=.9;camera.lookAt(look);dome.position.copy(camera.position);
  renderer.render(scene,camera);
  return {u,position:car.position.toArray(),camera:camera.position.toArray(),wheel:wheels[0].rotation.x,steer:front[0].rotation.y,indicator,blink,braking,wheels:wheels.length,...state};
 }
 return {scene,camera,pose,dispose(){
   const geometries=new Set(),materials=new Set(),textures=new Set();
   scene.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)for(const m of [].concat(o.material))materials.add(m)});
   for(const m of materials){for(const v of Object.values(m))if(v?.isTexture)textures.add(v);m.dispose()}
   geometries.forEach(g=>g.dispose());textures.forEach(t=>t.dispose());sun.shadow.dispose();reflection.dispose();
 }};
}
