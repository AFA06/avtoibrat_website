// Original coachbuilt fastback, in metres. Front is +Z. Wheel pivots are exported in the GLB.
import * as T from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { writeFile } from 'node:fs/promises';
globalThis.FileReader = class {
  async readAsArrayBuffer(blob) { this.result = await blob.arrayBuffer(); this.onloadend?.(); }
};
const car = new T.Group(), shell = new T.Group();
car.add(shell); shell.name='Coachwork';
function material(name,color,metalness,roughness) {
  const m=new T.MeshStandardMaterial({color,metalness,roughness,side:T.DoubleSide}); m.name=name;return m;
}
const paint=material('Cinnabar lacquer',0xbb3421,.67,.24), glass=material('Smoked glass',0x19313a,.75,.12);
const trim=material('Graphite',0x171c20,.3,.35), chrome=material('Brushed alloy',0xbcc5ca,.88,.23);
const rubber=material('Tyres',0x16191b,0,.84), lamp=material('Daylight strip',0xfff1ca,.05,.2), red=material('Rear light',0x92180d,.15,.22);
lamp.emissive.setHex(0xffcda0);red.emissive.setHex(0x8a1509);
function mesh(g,m,parent=shell){const o=new T.Mesh(g,m);parent.add(o);return o}
function block(x,y,z,w,h,d,m,parent=shell){const o=mesh(new T.BoxGeometry(w,h,d),m,parent);o.position.set(x,y,z);return o}
function tube(points,r,m,parent=shell){const curve=new T.CatmullRomCurve3(points.map(v=>new T.Vector3(...v)));return mesh(new T.TubeGeometry(curve,Math.max(10,points.length*4),r,6,false),m,parent)}
function loft(rings,m) {
 const vertices=rings.flat(2), indexes=[], n=rings[0].length;
 for(let i=0;i<rings.length-1;i++)for(let j=0;j<n;j++){let a=i*n+j,b=i*n+(j+1)%n;indexes.push(a,b,a+n,b,b+n,a+n)}
 for(let j=1;j<n-1;j++) indexes.push(0,j+1,j,(rings.length-1)*n,(rings.length-1)*n+j,(rings.length-1)*n+j+1);
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(vertices,3));g.setIndex(indexes);g.computeVertexNormals();return mesh(g,m);
}
function sample(keys,z,col){let j=1;while(j<keys.length-1&&z>keys[j][0])j++;const a=keys[j-1],b=keys[j];return T.MathUtils.lerp(a[col],b[col],T.MathUtils.clamp((z-a[0])/(b[0]-a[0]),0,1))}
const belt=[[-2.32,.73,.70],[-2.18,.90,.84],[-1.68,.95,.91],[-.7,.92,.86],[.64,.94,.86],[1.43,.96,.85],[2.03,.89,.72],[2.31,.74,.62]];
const rings=[];
for(let i=0;i<=110;i++){
 const z=-2.32+4.63*i/110,w=sample(belt,z,1),h=sample(belt,z,2);
 const dz=Math.min(Math.abs(z+1.43),Math.abs(z-1.43));
 const arch=dz<.393?.35+Math.sqrt(.393**2-dz**2):.29;
 const half=[[0,h+.035],[w*.74,h+.018],[w*.94,h-.015],[w,h-.08],[w*.995,arch],[w*.77,arch-.015],[w*.72,.24],[0,.23]];
 const ring=[...half,...half.slice(1,-1).reverse().map(([x,y])=>[-x,y])].map(([x,y])=>[x,y,z]);rings.push(ring);
}
loft(rings,paint);
const roof=[[-1.66,.79,.90],[-1.29,.75,1.11],[-.83,.68,1.39],[-.55,.65,1.46],[.24,.65,1.45],[.49,.68,1.35],[1.06,.83,.87]];
loft(roof.map(([z,w,h])=>[[0,h+.023,z],[w*.90,h,z],[w,h-.045,z],[.854,.867,z],[-.854,.867,z],[-w,h-.045,z],[-w*.90,h,z]]),glass);
loft([[-.82,.55,1.394],[-.56,.63,1.47],[.22,.63,1.46],[.34,.54,1.42]].map(([z,w,h])=>[[0,h+.023,z],[w,h,z],[w,h-.019,z],[-w,h-.019,z],[-w,h,z]]),paint);
for(const s of [-1,1]){
 tube(roof.map(([z,w,h])=>[s*w,h-.027,z]),.036,paint);
 tube([[-1.62,.91],[-.9,.895],[.15,.884],[1.05,.88]].map(([z,y])=>[s*.86,y,z]),.015,chrome);
 tube([[s*.845,.88,-.46],[s*.68,1.40,-.47]],.041,trim);
 tube([[s*.91,.845,-.85],[s*.929,.60,-.79],[s*.92,.34,-.72],[s*.924,.32,.70],[s*.946,.61,.77],[s*.927,.842,.74]],.008,trim);
 block(s*.927,.80,-.57,.026,.031,.17,chrome);
 block(s*.945,.34,0,.044,.055,1.9,trim);
 tube([[s*.81,.90,.65],[s*.99,.99,.60]],.035,trim);
 const mirror=mesh(new T.SphereGeometry(1,16,10),paint);mirror.scale.set(.16,.076,.12);mirror.position.set(s*1.024,1.008,.6);
 tube([[s*.48,.625,2.302],[s*.68,.659,2.267],[s*.82,.70,2.15],[s*.864,.725,2.04]],.027,lamp);
 tube([[s*.05,.699,-2.328],[s*.60,.70,-2.322],[s*.86,.79,-2.15]],.023,red);
 tube([[s*.40,.868,.99],[s*.50,.862,1.5],[s*.50,.732,2.01]],.009,paint);
}
block(0,.402,2.30,1.16,.159,.02,trim);for(let i=-2;i<=2;i++)block(0,.407+i*.025,2.314,1.10,.008,.012,chrome);
block(0,.423,-2.325,.47,.126,.024,chrome);
block(0,.305,-2.30,1.28,.10,.07,trim);
function mergeParts(group){
 const batches=new Map();
 for(const child of group.children.slice()){
  if(!child.isMesh)continue;
  child.updateMatrix();let g=child.geometry.index?child.geometry.toNonIndexed():child.geometry.clone();g.applyMatrix4(child.matrix);g.deleteAttribute('uv');
  if(!batches.has(child.material))batches.set(child.material,[]);batches.get(child.material).push(g);group.remove(child);
 }
 for(const [m,parts] of batches)mesh(mergeGeometries(parts),m,group);
}
mergeParts(shell);
for(const s of [-1,1])for(const z of [-1.43,1.43]){
 const pivot=new T.Group();pivot.name='Knuckle_'+(z>0?'F':'R')+(s>0?'R':'L');pivot.position.set(s*.835,.35,z);car.add(pivot);
 const wheel=new T.Group();wheel.name='Wheel_'+pivot.name.slice(8);pivot.add(wheel);
 function cyl(radius,depth,m,x){const o=mesh(new T.CylinderGeometry(radius,radius,depth,40),m,wheel);o.rotation.z=Math.PI/2;o.position.x=s*x}
 cyl(.35,.216,rubber,0);cyl(.259,.219,trim,0);cyl(.195,.016,trim,.112);
 const lip=mesh(new T.TorusGeometry(.241,.013,8,48),chrome,wheel);lip.rotation.y=Math.PI/2;lip.position.x=s*.119;
 for(let i=0;i<10;i++){const a=i*Math.PI/5;const o=block(s*.127,Math.sin(a)*.14,Math.cos(a)*.14,.019,.028,.194,chrome,wheel);o.rotation.x=-a+.22}
 cyl(.062,.033,trim,.14);mergeParts(wheel);
}
const data=await new GLTFExporter().parseAsync(car,{binary:true});
await writeFile(new URL('../../core/static/site/drive/fastback.glb',import.meta.url),Buffer.from(data));
