import * as T from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import {at,frame} from './road.js';
const cube=new T.BoxGeometry(), pole=new T.CylinderGeometry(1,1,1,12);
const stone=mat(0xc5a988), plaster=mat(0xdec9ac), dark=mat(0x293b3d), brass=mat(0xa77d48);
const leaf=mat(0x4b6955), leafLight=mat(0x78917a), bark=mat(0x69534a);
const bulb=new T.MeshBasicMaterial({color:0xffe1a7}), white=mat(0xdacdb5);
function mat(color){return new T.MeshStandardMaterial({color,roughness:.76})}
function piece(parent,g,m,x,y,z,w,h,d){const a=new T.Mesh(g,m);a.position.set(x,y,z);a.scale.set(w,h,d);parent.add(a);return a}
const box=(parent,m,x,y,z,w,h,d)=>piece(parent,cube,m,x,y,z,w,h,d);
function batch(group){
 const materials=new Map();for(const mesh of [...group.children]){
  if(!mesh.isMesh)continue;mesh.updateMatrix();const g=mesh.geometry.index?mesh.geometry.toNonIndexed():mesh.geometry.clone();g.applyMatrix4(mesh.matrix);
  if(!materials.has(mesh.material))materials.set(mesh.material,[]);materials.get(mesh.material).push(g);group.remove(mesh);
 }
 for(const [m,parts] of materials){const geo=mergeGeometries(parts);parts.forEach(g=>g.dispose());group.add(new T.Mesh(geo,m))}
}
function texture(draw,w=512,h=512){const c=document.createElement('canvas');c.width=w;c.height=h;draw(c.getContext('2d'),w,h);const tex=new T.CanvasTexture(c);tex.colorSpace=T.SRGBColorSpace;return tex}
function facade(variant){
 const tex=texture((ctx,w,h)=>{
 ctx.fillStyle=['#a99886','#c0b29c','#6f7874'][variant];ctx.fillRect(0,0,w,h);
 const floors=variant===2?8:5,cols=variant===1?5:8;
 for(let iy=0;iy<floors;iy++)for(let ix=0;ix<cols;ix++){
 const cw=w/cols,ch=h/floors,x=ix*cw+cw*.09,y=iy*ch+ch*.08;
 const glass=ctx.createLinearGradient(x,y,x+cw*.8,y+ch*.7);
 const lit=(ix*17+iy*7+variant)%9<2;
 glass.addColorStop(0,lit?'#d8b48b':'#719297');glass.addColorStop(.4,lit?'#c29469':'#537682');glass.addColorStop(1,lit?'#997653':'#334c52');
 ctx.fillStyle='#394345';ctx.fillRect(x-2,y-2,cw*.84+3,ch*.76+3);ctx.fillStyle=glass;ctx.fillRect(x,y,cw*.83,ch*.75);
 ctx.fillStyle='#344547';ctx.fillRect(x+cw*.39,y,2,ch*.75);ctx.fillRect(x,y+ch*.20,cw*.83,2);
 ctx.fillStyle='#e1cfaf';ctx.fillRect(ix*cw,(iy+1)*ch-4,cw,4);
 }});
 return new T.MeshStandardMaterial({map:tex,roughness:.56});
}
function board(text,width=512){
 const tex=texture((c,w,h)=>{c.fillStyle='#243e3e';c.fillRect(0,0,w,h);c.fillStyle='#eee1c5';c.textAlign='center';c.textBaseline='middle';c.font='600 '+Math.round(h*.55)+'px sans-serif';c.fillText(text,w/2,h*.51,w*.92)},width,80);
 return new T.MeshBasicMaterial({map:tex,side:T.DoubleSide});
}
function softShadow(){
 const tex=texture((c,w,h)=>{const grad=c.createRadialGradient(w/2,h/2,0,w/2,h/2,w/2);grad.addColorStop(0,'rgba(0,0,0,.87)');grad.addColorStop(.60,'rgba(0,0,0,.63)');grad.addColorStop(1,'rgba(0,0,0,0)');c.fillStyle=grad;c.fillRect(0,0,w,h)},96,96);
 return new T.MeshBasicMaterial({map:tex,transparent:true,depthWrite:false,color:0x292120});
}
export function carShadow(car){const o=new T.Mesh(new T.PlaneGeometry(3.05,5.9),softShadow());o.rotation.x=-Math.PI/2;o.position.y=.023;car.add(o)}
export function districts(scene){
 const facades=[0,1,2].map(facade),buildings=[],fixed=new T.Group(),street=new T.Group(),yard=new T.Group();
 scene.add(fixed,street,yard);
 // A boulevard lined with colonnades and projecting horizontal sun shades.
 for(const side of [-1,1])for(let i=-3;i<9;i++){
  if(i===5||i===6&&side===1)continue;
  const variant=(i+6+(side===1?1:0))%3,z=23-i*12.8;
  const g=new T.Group();g.position.set(side*(15+(i+4)%3),0,z);g.rotation.y=side<0?Math.PI/2:-Math.PI/2;
  const h=8+((i+5)*7+(side+1)*4)%13,w=10.7,d=6.4;
  box(g,stone,0,.20,1,w+3,.4,d+4);
  box(g,facades[variant],0,h/2+2,0,w,h,d);
  box(g,dark,0,1.45,0,w*.98,2.8,d*.96);
  for(let j=-2;j<=2;j++)box(g,plaster,j*w*.22,1.65,d*.61,.31,3.25,.4);
  box(g,stone,0,3.18,d*.52,w+1,.34,2.15);
  for(let j=0;j<=3;j++)box(g,variant===2?dark:plaster,0,3+j*(h-1)/3,0,w+.4,.18,d+.4);
  box(g,plaster,0,h+2.12,0,w+.5,.25,d+.5);
  box(g,stone,-w*.18,h+2.69,-.3,w*.42,1.1,d*.50);
  if(variant===1){for(let j=-2;j<=2;j++)box(g,stone,j*w*.23,h/2+2,d*.51,.18,h,.38)}
  batch(g);scene.add(g);buildings.push({g,z});
 }
 // Shared street furniture is batched once for the entire district.
 const tree=new T.IcosahedronGeometry(1,1);
 for(let i=-4;i<16;i++)for(const side of [-1,1]){
 const z=20-i*6;if(Math.abs(z+49)<10)continue;
 const x=side*((side<0?11.2:9.2)+(i%2)*.25);piece(fixed,pole,bark,x,1.55,z,.13,3.1,.13);
 piece(fixed,tree,i%3?leaf:leafLight,x,3.9,z,1.05,2.35,1.02);
 if(i%3===0){box(street,dark,side*6.8,2.75,z,.105,5.5,.105);box(street,dark,side*6.1,5.52,z,1.5,.09,.12);box(street,bulb,side*5.48,5.46,z,.40,.06,.23)}
 }
 for(const side of [-1,1])for(const [z,d] of [[19,116],[-83,53]]){
 box(fixed,stone,side*8.5,.11,z,5.2,.22,d);
 box(fixed,plaster,side*6.04,.15,z,.30,.31,d);
 }
 // Cross street, pedestrian stripes and signal facing approaching traffic.
 box(fixed,mat(0x42464c),0,.008,-48,80,.016,9);
 for(let i=0;i<10;i++)box(fixed,white,-4.7+i*1.04,.042,-39,.48,.018,2.25);
 box(fixed,white,2.7,.045,-36.8,4.9,.018,.18);
 box(fixed,dark,5.4,2.6,-40,.15,5.2,.15);box(fixed,dark,5.4,4.5,-40,.70,1.68,.47);
 const lights=[0xff4827,0xffb94a,0x4ae49a].map((color,i)=>{
 const m=new T.MeshBasicMaterial({color});const node=piece(scene,new T.SphereGeometry(1,12,8),m,5.4,5.04-i*.51,-39.74,.21,.21,.09);return {node,color:new T.Color(color)}
 });
 // Priority-road sign on the approach, also reproduced in the school’s sign exercise.
 const sign=new T.Group();sign.position.set(5.7,0,-33);box(sign,dark,0,1.2,0,.08,2.4,.08);
 const plate=box(sign,white,0,2.68,0,.88,.88,.07);plate.rotation.z=Math.PI/4;
 const yellow=box(sign,mat(0xf5bd3a),0,2.68,.047,.68,.68,.02);yellow.rotation.z=Math.PI/4;
 batch(sign);scene.add(sign);
 // Contoured ridges behind the foothill road, well outside the drivable area.
 const ridgeColors=[0xa8b2a3,0x849b89,0x657e6d];
 for(let layer=0;layer<3;layer++){
 const p=[],idx=[];for(let j=0;j<=100;j++){
 const x=-340+j*8,z=-230+layer*38;
 const h=14+(2-layer)*7+7*Math.sin(j*.33+layer*2)+4*Math.sin(j*.91)+3*Math.cos(j*1.61);
 p.push(x,-2,z,x,h,z-9);if(j){const k=j*2;idx.push(k-2,k-1,k,k,k-1,k+1)}
 }
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(p,3));g.setIndex(idx);g.computeVertexNormals();const m=mat(ridgeColors[layer]);m.side=T.DoubleSide;scene.add(new T.Mesh(g,m));
 }
 for(let i=0;i<52;i++){const u=.50+i*.0087,s=i%2?1:-1,p=at(u,s*(17+(i*7)%20));piece(fixed,tree,i%3?leaf:leafLight,p.x,2.2,p.z,1.25,2.9,1.36)}
 // Training court with a canopy, marked bays, cones and a low glass pavilion.
 yard.position.set(137,0,-59);
 box(yard,mat(0x686862),0,.003,0,53,.006,39);
 box(yard,facades[0],0,2,-14,23,4,5.4);box(yard,dark,0,4.22,-13.1,26,.38,8);
 for(const x of [-11,-5,5,11])box(yard,stone,x,2,-10,.24,4,.24);
 const name=new T.Mesh(new T.PlaneGeometry(6.9,1.08),board('AVTOIBRAT'));name.position.set(0,3,-11.25);yard.add(name);
 const cone=new T.ConeGeometry(1,1,16),orange=mat(0xf76538);
 for(let j=0;j<11;j++){const x=-19+j*3.7;box(yard,white,x,.025,11,.10,.02,4.6);piece(yard,cone,orange,x,.31,6,.24,.62,.24);piece(yard,cone,white,x,.40,6,.14,.35,.14);box(yard,trimMat(),x,.06,6,.55,.12,.55)}
 batch(yard);batch(street);batch(fixed);
 const smooth=T.MathUtils.smoothstep;
 return {yard,lights,update(p,opening){
  for(const {g,z} of buildings){
    const reveal=z< -10?.05+(-z-10)*.002:0;
    const grow=reveal?smooth(p,reveal,reveal+.09):.87+.13*opening;
    const retreat=1-smooth(p,.57+Math.abs(z%13)*.003,.73+Math.abs(z%13)*.003);
    g.scale.y=Math.max(.001,grow*retreat);g.visible=g.scale.y>.01;
  }
  street.scale.y=.84+.16*opening;yard.scale.y=.001+.999*smooth(p,.65,.83);
  const signal=p<.45?0:p<.48?1:2;
  lights.forEach(({node,color},i)=>node.material.color.copy(color).multiplyScalar(i===signal?1.6:.12));
  return {building:buildings.find(v=>v.z< -20).g.scale.y,signal,training:yard.scale.y};
 }};
}
let black;
function trimMat(){return black??=mat(0x303335)}
