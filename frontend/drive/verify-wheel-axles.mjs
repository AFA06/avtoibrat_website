// Check the exported tyre geometry, rather than just animation state.
import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const bytes=await readFile(new URL('../../core/static/site/drive/gentra.glb',import.meta.url));
const {scene}=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
const wheels=[];scene.traverse(o=>{if(o.name.startsWith('Wheel_'))wheels.push(o)});
assert.equal(wheels.length,4);
for(const wheel of wheels){
 const tyre=wheel.children[0].geometry.attributes.position,mean=new T.Vector3(),v=new T.Vector3();
 for(let i=0;i<tyre.count;i++)mean.add(v.fromBufferAttribute(tyre,i));mean.divideScalar(tyre.count);
 let xy=0,xz=0;
 for(let i=0;i<tyre.count;i++){v.fromBufferAttribute(tyre,i).sub(mean);xy+=v.x*v.y/tyre.count;xz+=v.x*v.z/tyre.count}
 assert(Math.abs(xy)<.00005 && Math.abs(xz)<.00005,`${wheel.name}: tyre axle must be straight, not tilted`);
 const centers=[],radii=[];
 for(const angle of [0,Math.PI/2,Math.PI,Math.PI*1.5,Math.PI*2]){
  const box=new T.Box3();
  for(let i=0;i<tyre.count;i++)box.expandByPoint(v.fromBufferAttribute(tyre,i).applyAxisAngle(new T.Vector3(1,0,0),angle));
  centers.push(box.getCenter(new T.Vector3()));radii.push((box.max.y-box.min.y)/2);
 }
 assert(centers.every(c=>Math.hypot(c.y,c.z)<.002),`${wheel.name}: tyre must rotate around its hub`);
 assert(Math.max(...radii)-Math.min(...radii)<.002,`${wheel.name}: rolling tyre must stay planted`);
 console.log(`${wheel.name}: straight axle, centered hub and stable tyre radius passed`);
}
