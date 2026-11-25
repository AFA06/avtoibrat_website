import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {DRACOLoader} from 'three/addons/loaders/DRACOLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';

const root=document.querySelector('.driving-universe');
if(root){
const base=root.dataset.assets, layer=root.querySelector('.universe-canvas'), panels=[...root.querySelectorAll('[data-course]')], nav=[...root.querySelectorAll('[data-world]')];
const reduce=matchMedia('(prefers-reduced-motion: reduce)'), pause=root.querySelector('.universe-motion');
let renderer,scene,camera,env,disposed=false,raf=0,visible=false,paused=false,ready=false,active=0,flight=null,scroll=0,pointer={x:0,y:0},lastTime=0;
const worlds=[],point=new THREE.Vector3(),look=new THREE.Vector3();
const definitions={B:{color:'#fa7651',label:'MALIBU',position:[6.3,2.15,8.8],target:[1.6,.65,0],fov:35},A:{color:'#a2d9d9',label:'SUPERSPORT',position:[2.8,1.25,4.3],target:[.9,.6,0],fov:37},BC:{color:'#b7c4e0',label:'TOGETHER',position:[10,3,15.5],target:[2,1.2,0],fov:35},C:{color:'#eab96b',label:'ISUZU',position:[7.5,1.3,11.6],target:[2.2,1.4,0],fov:36}};
const initial=nav.findIndex(a=>a.hash===location.hash);if(initial>=0)active=initial;
const textureLoader=new THREE.TextureLoader(), truckFrames=new Map();
function frameTexture(index,kind='truck'){index=(index+24)%24;const key=kind+index;if(!truckFrames.has(key))truckFrames.set(key,textureLoader.loadAsync(base+`${kind}/view-${String(index).padStart(2,'0')}.webp`).then(t=>{t.colorSpace=THREE.SRGBColorSpace;return t;}));return truckFrames.get(key);}
function shadow(x,z,w,d){const c=document.createElement('canvas');c.width=c.height=128;const g=c.getContext('2d'),gradient=g.createRadialGradient(64,64,5,64,64,64);gradient.addColorStop(0,'rgba(0,0,0,.8)');gradient.addColorStop(1,'rgba(0,0,0,0)');g.fillStyle=gradient;g.fillRect(0,0,128,128);const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,d),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(c),transparent:true,depthWrite:false}));mesh.rotation.x=-Math.PI/2;mesh.position.set(x,.015,z);mesh.renderOrder=2;return mesh;}
function lettering(text,color){const c=document.createElement('canvas');c.width=2048;c.height=1024;const g=c.getContext('2d');g.font='800 850px Atlas,Arial';g.textAlign='center';g.textBaseline='middle';g.fillStyle=color;g.fillText(text,1024,545,1960);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;return new THREE.Mesh(new THREE.PlaneGeometry(17,8.5),new THREE.MeshBasicMaterial({map:t,transparent:true,opacity:.55,depthWrite:false}));}
function bar(w,h,d,color){return new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color,roughness:.55,metalness:.28}));}
function makeBay(category,index){const def=definitions[category]||definitions.B,group=new THREE.Group();group.position.x=index*28;scene.add(group);const word=lettering(category,def.color);word.position.set(-.3,4.2,-4.5);group.add(word);
 const portal=new THREE.Group();portal.position.set(0,0,-5.4);portal.rotation.z=category==='A'?-.22:0;group.add(portal);
 const width=category==='BC'?18:13;
 for(const side of [-1,1]){const fin=bar(.16,8,.3,'#2f3337');fin.position.set(side*width/2,4,0);portal.add(fin);const strip=new THREE.Mesh(new THREE.BoxGeometry(.035,7.8,.04),new THREE.MeshBasicMaterial({color:def.color}));strip.position.set(side*width/2-side*.09,4,.2);portal.add(strip);}
 const ceiling=bar(width,.16,.3,'#30363b');ceiling.position.y=8;portal.add(ceiling);
 const light=new THREE.PointLight(def.color,40,23,2);light.position.set(-4,4,-3);group.add(light);
 const edge=new THREE.Mesh(new THREE.PlaneGeometry(24,.025),new THREE.MeshBasicMaterial({color:def.color}));edge.rotation.x=-Math.PI/2;edge.rotation.z=category==='A'?.45:0;edge.position.set(0,.025,-2.6);group.add(edge);
 const details=[];for(let i=0;i<5;i++){const fin=bar(.12,7,.3,'#171b20');fin.position.set(-10+i*5.2,3.5,-14);group.add(fin);details.push(fin);}

 if(category==='B'){
   const halo=new THREE.Mesh(new THREE.TorusGeometry(5.6,.035,8,96,Math.PI*1.55),new THREE.MeshBasicMaterial({color:'#d98e71'}));halo.position.set(-1,2,-7);halo.rotation.z=-.35;group.add(halo);portal.visible=false;details.forEach(f=>f.visible=false);
 }else if(category==='A'){
   portal.rotation.z=-.3;portal.position.z=-4;
   for(let i=0;i<3;i++){const rail=new THREE.Mesh(new THREE.BoxGeometry(.035,8,.035),new THREE.MeshBasicMaterial({color:'#90d4d5'}));rail.position.set(3+i*1.4,3,-4-i*2);rail.rotation.z=-.35;group.add(rail);}
 }else if(category==='BC'){
   word.position.set(-1.6,4.9,-6.6);word.scale.setScalar(1.1);
   for(const x of [-4,4]){const strip=new THREE.Mesh(new THREE.PlaneGeometry(.025,30),new THREE.MeshBasicMaterial({color:'#8e9bb4'}));strip.rotation.x=-Math.PI/2;strip.position.set(x,.03,-6);group.add(strip);}
 }else if(category==='C'){
   portal.position.z=-7;portal.scale.set(1.3,.9,1);word.position.set(-.3,5,-8);
   for(let i=0;i<3;i++){const roof=bar(16,.18,1.2,'#222427');roof.position.set(0,8,-3-i*4);group.add(roof);}
 }
 const world={category,group,def,word,portal,light,trucks:[],cars:[],mirrors:[]};worlds.push(world);return world;
}
function normalized(gltf,length){const object=gltf.scene.clone(true);object.updateMatrixWorld(true);let bounds=new THREE.Box3().setFromObject(object),size=bounds.getSize(new THREE.Vector3());if(size.x>size.z)object.rotation.y=Math.PI/2;object.updateMatrixWorld(true);bounds=new THREE.Box3().setFromObject(object);size=bounds.getSize(new THREE.Vector3());const scale=length/Math.max(size.x,size.z);object.scale.multiplyScalar(scale);object.updateMatrixWorld(true);bounds=new THREE.Box3().setFromObject(object);const center=bounds.getCenter(new THREE.Vector3());const wrap=new THREE.Group();object.position.sub(new THREE.Vector3(center.x,bounds.min.y,center.z));wrap.add(object);
 object.traverse(mesh=>{if(!mesh.isMesh)return;mesh.castShadow=true;mesh.receiveShadow=true;const mats=Array.isArray(mesh.material)?mesh.material:[mesh.material];const revised=mats.map(m=>{let material=m.clone();material.envMapIntensity=1.15;
if(material.name==='int_mat'||/Fairing paint/.test(material.name)){
 const paint=new THREE.MeshPhysicalMaterial();THREE.MeshStandardMaterial.prototype.copy.call(paint,material);material=paint;
 material.color.set(material.name==='int_mat'?'#253039':'#171e24');material.metalness=.55;material.roughness=.23;material.clearcoat=1;material.clearcoatRoughness=.14;
}
if(material.name==='lights'&&material.map){material.emissiveMap=material.map;material.emissive=new THREE.Color('#e6efff');material.emissiveIntensity=.65;}
if(/glass/i.test(material.name)){material.roughness=.12;material.metalness=.25;material.transparent=true;material.opacity=.65;material.depthWrite=false;}return material;});mesh.material=Array.isArray(mesh.material)?revised:revised[0];});return wrap;}
function addCar(world,gltf,x,z,length,rotation){const model=normalized(gltf,length);model.position.set(x,0,z);model.rotation.y=rotation;world.group.add(model);world.cars.push(model);
if(length>4){for(const x of [-.63,.63]){const lamp=new THREE.SpotLight('#e6efff',14,13,.25,.7,1);lamp.position.set(x,.62,2.25);lamp.target.position.set(x,.02,8);model.add(lamp,lamp.target);}}
world.group.add(shadow(x,z,length*.6,length*1.15));const reflected=model.clone(true);reflected.scale.y=-1;reflected.position.y=-.035;reflected.traverse(m=>{if(!m.isMesh)return;m.castShadow=false;m.receiveShadow=false;const dim=mat=>{const a=mat.clone();a.transparent=true;a.opacity=.14;a.depthWrite=false;return a;};m.material=Array.isArray(m.material)?m.material.map(dim):dim(m.material);});world.group.add(reflected);world.mirrors.push(reflected);return model;}
async function addRendered(world,x,z,scale=1,kind='truck'){
 const bike=kind==='bike',width=(bike?2.7:7.1)*scale,height=(bike?1.91:4.93)*scale;
 const mat=new THREE.SpriteMaterial({map:await frameTexture(bike?4:10,kind),transparent:true,depthWrite:false,color:bike?'#f4eeee':'#ddd5ce'}),sprite=new THREE.Sprite(mat);
 sprite.material.depthTest=false;sprite.renderOrder=5;sprite.center.set(.5,0);sprite.position.set(x,.015,z);sprite.scale.set(width,height,1);world.group.add(sprite);
 const mirror=new THREE.Sprite(mat.clone());mirror.material.opacity=.28;mirror.material.depthTest=false;mirror.renderOrder=-1;mirror.center.set(.5,0);mirror.position.set(x,-.035,z);mirror.scale.set(width,-height,1);world.group.add(mirror);
 world.group.add(shadow(x,z,bike?1.1:2.8*scale,bike?2.1:5.4*scale));world.trucks.push({sprite,mirror,index:bike?4:10,requested:bike?4:10,kind});
}
function cameraPose(index,entrance=true){const world=worlds[index],def=world.def,mobile=innerWidth<=650;const p=new THREE.Vector3(...def.position),target=new THREE.Vector3(...def.target);
 if(mobile){p.multiplyScalar({A:1.2,B:1.3,BC:1.9,C:1.9}[world.category]||1.3);target.x=0;target.y=world.category==='C'?1.4:.9;}
 p.x+=world.group.position.x;target.x+=world.group.position.x;
 if(entrance&&!reduce.matches){const q=Math.max(0,1-scroll*2.8);p.x+=q*5;p.y+=q*3;p.z+=q*8;}
 return {p,target,fov:def.fov+(mobile?10:0)};}
function schedule(){if(!raf&&(visible||flight)&&!document.hidden&&!disposed)raf=requestAnimationFrame(render);}
function updateTruck(world){for(const t of world.trucks){const position=world.group.localToWorld(t.sprite.position.clone()),angle=Math.atan2(camera.position.x-position.x,camera.position.z-position.z);const index=((Math.round(angle/(Math.PI*2)*24)+(t.kind==='bike'?2:12))%24+24)%24;if(index===t.requested)continue;t.requested=index;frameTexture(index,t.kind).then(map=>{if(disposed||t.requested!==index)return;t.sprite.material.map=map;t.mirror.material.map=map;t.index=index;schedule();});}}
function render(time){raf=0;if(disposed||(!visible&&!flight)||!ready)return;lastTime=time;const pose=cameraPose(active),world=worlds[active];
 if(flight){const t=flight.hold??THREE.MathUtils.clamp((time-flight.start)/2200,0,1),e=t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;point.copy(flight.from).lerp(pose.p,e);look.copy(flight.target).lerp(pose.target,e);point.y+=Math.sin(Math.PI*t)*2.9;point.z+=Math.sin(Math.PI*t)*16;camera.fov=THREE.MathUtils.lerp(flight.fov,pose.fov,e)+Math.sin(Math.PI*t)*12;if(t>=1)flight=null;
 }else{point.copy(pose.p);look.copy(pose.target);camera.fov=pose.fov;if(!reduce.matches&&!paused){point.x+=pointer.x*.42;point.y+=pointer.y*.18;}}
 camera.position.copy(point);camera.lookAt(look);if(innerWidth<=650){camera.setViewOffset(layer.clientWidth,layer.clientHeight,0,layer.clientHeight*.15,layer.clientWidth,layer.clientHeight);}else camera.clearViewOffset();camera.updateProjectionMatrix();
 worlds.forEach(w=>{w.group.visible=Math.abs(camera.position.x-w.group.position.x)<38;w.word.rotation.y=(camera.position.x-w.group.position.x)*.012;w.light.intensity=28+(w===world?14:0);if(w.group.visible)updateTruck(w);});
 const key=scene.userData.key;key.position.x=camera.position.x+2;key.target.position.x=camera.position.x-5;key.target.updateMatrixWorld();
 renderer.render(scene,camera);root.dataset.transition=flight?'moving':'settled';
 if(flight&&flight.hold===undefined)schedule();
}
function select(index,animate=true){if(index===active&&ready&&animate)return;const before=active;active=index;const world=worlds[index];root.style.setProperty('--u-accent',world.def.color);nav.forEach((a,i)=>{if(i===index)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current');});panels.forEach((p,i)=>{p.hidden=i!==index;});if(animate&&ready&&!reduce.matches&&!paused){flight={from:camera.position.clone(),target:look.clone(),fov:camera.fov,start:performance.now()};const copy=root.querySelector('.universe-copy');copy.getAnimations().forEach(a=>a.cancel());copy.animate([{opacity:1,transform:'perspective(700px) rotateY(-6deg)'},{opacity:.12,offset:.3,transform:'perspective(700px) rotateY(12deg)'},{opacity:1,transform:'none'}],{duration:1900,easing:'cubic-bezier(.4,0,.2,1)'});}else flight=null;root.dataset.category=world.category;visible=!document.hidden&&root.getBoundingClientRect().bottom>0&&root.getBoundingClientRect().top<innerHeight;schedule();}
function onScroll(){const r=root.getBoundingClientRect(),available=Math.max(1,root.offsetHeight-innerHeight+72);scroll=THREE.MathUtils.clamp(-r.top/available,0,1);root.querySelector('.universe-scroll-track span').style.transform=`scaleX(${scroll})`;schedule();}
function resize(){if(!renderer)return;const w=layer.clientWidth,h=layer.clientHeight;renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth<=650?1.25:1.5));renderer.shadowMap.enabled=innerWidth>650;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();schedule();}
async function init(){if(renderer||disposed)return;try{
 renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth<=650?1.25:1.5));renderer.setClearColor('#131416',1);renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.1;renderer.shadowMap.enabled=innerWidth>650;renderer.shadowMap.type=THREE.PCFSoftShadowMap;layer.append(renderer.domElement);
 scene=new THREE.Scene();scene.fog=new THREE.FogExp2('#131416',.022);camera=new THREE.PerspectiveCamera(35,1,.1,160);
 const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();env=pmrem.fromScene(room,.04);scene.environment=env.texture;room.dispose();pmrem.dispose();
 scene.add(new THREE.HemisphereLight('#a7bdce','#0c0909',.8));const key=new THREE.DirectionalLight('#fff3df',3.2);key.position.set(5,10,5);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-14;key.shadow.camera.right=14;key.shadow.camera.top=14;key.shadow.camera.bottom=-14;key.shadow.bias=-.001;scene.add(key,key.target);scene.userData.key=key;
 const fill=new THREE.DirectionalLight('#a3bbd3',.85);fill.position.set(-8,4,-3);scene.add(fill);
 const floor=new THREE.Mesh(new THREE.PlaneGeometry(180,100),new THREE.MeshStandardMaterial({color:'#111519',roughness:.3,metalness:.3,transparent:true,opacity:.87}));floor.rotation.x=-Math.PI/2;floor.position.set(40,-.02,0);floor.receiveShadow=true;scene.add(floor);
 for(let i=-3;i<13;i++){const seam=new THREE.Mesh(new THREE.PlaneGeometry(.018,45),new THREE.MeshBasicMaterial({color:'#3e4042',transparent:true,opacity:.35}));seam.rotation.x=-Math.PI/2;seam.position.set(i*8,.003,0);scene.add(seam);}
 await document.fonts.ready;panels.forEach((p,i)=>makeBay(p.dataset.course,i));
 const draco=new DRACOLoader().setDecoderPath(base+'decoders/draco/');const loader=new GLTFLoader().setDRACOLoader(draco);
 const malibu=await loader.loadAsync(base+'malibu.glb');
 await Promise.all(worlds.map(async w=>{if(w.category==='B')addCar(w,malibu,0,0,4.92,-.4);if(w.category==='A')await addRendered(w,0,0,1,'bike');if(w.category==='BC'){addCar(w,malibu,-2.7,1.4,4.92,-.3);await addRendered(w,2,-1.6,1);}if(w.category==='C')await addRendered(w,0,0,1.12);}));
 ready=true;root.dataset.ready='true';root.classList.add('is-enhanced');root.querySelector('.universe-load').textContent='';select(active,false);resize();onScroll();
 root.universeState=()=>({ready,visible,category:worlds[active].category,moving:!!flight,camera:camera.position.toArray(),target:look.toArray(),drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles});
 root.universeSeek=(fraction)=>{if(flight){flight.hold=fraction;schedule();}};
 root.universePlay=()=>{if(flight){flight.start=performance.now()-2200*(flight.hold||0);delete flight.hold;schedule();}};
 window.addEventListener('resize',resize,{passive:true});window.addEventListener('scroll',onScroll,{passive:true});root.addEventListener('pointermove',e=>{const r=root.getBoundingClientRect();pointer.x=(e.clientX-r.left)/r.width-.5;pointer.y=(e.clientY-r.top)/(root.querySelector('.universe-sticky').clientHeight)-.5;schedule();});
 nav.forEach((a,i)=>a.addEventListener('click',e=>{e.preventDefault();select(i);}));
 nav.forEach((a,i)=>a.addEventListener('keydown',e=>{if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?nav.length-1:(i+(e.key==='ArrowDown'?1:-1)+nav.length)%nav.length;select(next);nav[next].focus();}}));
 pause.addEventListener('click',()=>{paused=!paused;pause.setAttribute('aria-pressed',String(paused));pause.querySelector('i').className=paused?'ti ti-player-play':'ti ti-player-pause';if(paused)flight=null;schedule();});
 reduce.addEventListener('change',()=>{flight=null;resize();onScroll();});
 document.addEventListener('visibilitychange',()=>{visible=!document.hidden&&root.getBoundingClientRect().bottom>0&&root.getBoundingClientRect().top<innerHeight;if(visible)schedule();else{cancelAnimationFrame(raf);raf=0;}});
 }catch(error){console.error('Driving universe:',error);root.dataset.ready='error';root.querySelector('.universe-load').textContent='';layer.innerHTML='<span class="universe-static-title" aria-hidden="true">'+panels[active].dataset.course+'</span>';nav.forEach((a,i)=>a.addEventListener('click',e=>{e.preventDefault();panels.forEach((p,j)=>p.hidden=i!==j);nav.forEach((n,j)=>j===i?n.setAttribute('aria-current','true'):n.removeAttribute('aria-current'));layer.querySelector('span').textContent=panels[i].dataset.course;}));}
}
new IntersectionObserver(entries=>{const entry=entries[0];if(entry.isIntersecting)init();},{rootMargin:'650px'}).observe(root);
new IntersectionObserver(entries=>{visible=entries[0].isIntersecting&&!document.hidden;if(visible)schedule();else{cancelAnimationFrame(raf);raf=0;}}).observe(root);
}
