// Prepare the owner-supplied detailed Gentra. Front is +Z, dimensions in metres.
// Usage: node build-car.mjs [path/to/gentra.glb]
import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {mergeGeometries, mergeVertices} from 'three/addons/utils/BufferGeometryUtils.js';
import {readFile, writeFile} from 'node:fs/promises';
globalThis.FileReader=class {async readAsArrayBuffer(blob){this.result=await blob.arrayBuffer();this.onloadend?.()}};
const bytes=await readFile(process.argv[2] || new URL('../../gentra.glb',import.meta.url));
const {scene:source}=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
source.rotation.y=Math.PI;source.updateMatrixWorld(true);
const box=new T.Box3().setFromObject(source),center=box.getCenter(new T.Vector3());
const scale=4.515/(box.max.z-box.min.z);
const normalize=new T.Matrix4().makeScale(scale,scale,scale).multiply(new T.Matrix4().makeTranslation(-center.x,-box.min.y,-center.z));
const car=new T.Group();car.name='Chevrolet Gentra';
const shell=new T.Group();shell.name='Coachwork';car.add(shell);
const batches=new Map(),wheelRoots=[];
source.traverse(o=>{if(o.name.startsWith('wheel_rf_dummy'))wheelRoots.push(o)});
const tuned=new Map();
function material(original){
 if(tuned.has(original))return tuned.get(original);
 const m=original.clone();
 if(m.name==='primary'){m.color.setHex(0x101318);m.metalness=.65;m.roughness=.23;}
 else if(m.name.startsWith('unnamed')){const alloy=/[1357]$/.test(m.name);m.color.setHex(alloy?0xaab0b5:0x151719);m.metalness=alloy?.85:0;m.roughness=alloy?.26:.84;}
 else if(m.name==='chassis.0'||m.name==='glass.004'){m.color.setHex(0x1c2730);m.opacity=.80;m.roughness=.12;m.metalness=.25;m.depthWrite=false;}
 else if(['chassis.4','chassis.6','chassis.7','chassis.8','chassis.11'].includes(m.name)){m.color.setHex(0x121519);m.metalness=.35;m.roughness=.32;}
 else if(m.name==='chassis.9'){m.color.setHex(0x24272a);m.roughness=.8;}
 else if(m.name==='glass'){m.color.setHex(0x8d0a0a);m.opacity=.88;m.roughness=.22;}
 else if(m.name.startsWith('glass.00')){m.color.setHex(0xc4d1d8);m.roughness=.15;m.metalness=.4;m.transparent=true;m.opacity=.3;m.depthWrite=false;}
 else {m.roughness=Math.max(.22,m.roughness);if(m.name==='chassis.10'){m.metalness=.85;m.roughness=.23;}}
 tuned.set(original,m);return m;
}
function geometry(o){const g=o.geometry.clone();g.applyMatrix4(new T.Matrix4().multiplyMatrices(normalize,o.matrixWorld));for(const name of Object.keys(g.attributes))if(!['position','normal'].includes(name))g.deleteAttribute(name);return g;}
for(const root of wheelRoots){
 // The download has a baked toe angle on both left wheels. Remove it
 // from the mesh before animation, so rotation about X cannot wobble the tyre.
 const axle=new T.Vector3().setFromMatrixColumn(root.matrixWorld,0).transformDirection(normalize);
 if(axle.x<0)axle.negate();
 const straighten=new T.Quaternion().setFromUnitVectors(axle,new T.Vector3(1,0,0));
 const tyre=root.getObjectByProperty('isMesh',true);
 const bounds=new T.Box3().setFromObject(tyre).applyMatrix4(normalize),pivot=bounds.getCenter(new T.Vector3());
 const name=(pivot.z>0?'F':'R')+(pivot.x>0?'L':'R');
 const knuckle=new T.Group();knuckle.name='Knuckle_'+name;knuckle.position.copy(pivot);car.add(knuckle);
 const wheel=new T.Group();wheel.name='Wheel_'+name;knuckle.add(wheel);
 root.traverse(o=>{if(o.isMesh){const g=geometry(o);g.translate(-pivot.x,-pivot.y,-pivot.z);g.applyQuaternion(straighten);const mesh=new T.Mesh(mergeVertices(g),material(o.material));wheel.add(mesh)}});
}
source.traverse(o=>{
 if(!o.isMesh)return;for(let p=o.parent;p;p=p.parent)if(wheelRoots.includes(p))return;
 const g=geometry(o),m=material(o.material);
 const c=new T.Box3().setFromBufferAttribute(g.attributes.position).getCenter(new T.Vector3());
 let key=m.name;
 // Keep each side's actual factory lenses independently addressable.
 if(m.name.startsWith('povorotnikler'))key='Indicator_'+(c.x>0?'L':'R');
 else if(m.name==='right_front_light' && c.z>1.5)key='Headlamp';
 else if(m.name==='right_rear_light' || m.name==='arxa_stop.0')key='Brake';
 if(!batches.has(key))batches.set(key,{material:m.clone(),parts:[]});batches.get(key).parts.push(g);
});
for(const [name,batch] of batches){const mesh=new T.Mesh(mergeVertices(mergeGeometries(batch.parts)),batch.material);mesh.name=name;
 if(name.startsWith('Indicator')){mesh.material.color.setHex(0xffa01c);mesh.material.emissive.setHex(0xff7900);mesh.material.roughness=.24;}
 if(name==='Headlamp'){mesh.material.color.setHex(0xe7efff);mesh.material.emissive.setHex(0xdceaff);mesh.material.emissiveIntensity=.65;}
 if(name==='Brake'){mesh.material.color.setHex(0x9a0b07);mesh.material.emissive.setHex(0xff1608);}
 shell.add(mesh);
}
const data=await new GLTFExporter().parseAsync(car,{binary:true});
await writeFile(new URL('../../core/static/site/drive/gentra.glb',import.meta.url),Buffer.from(data));
console.log(`Gentra: ${(data.byteLength/1048576).toFixed(1)} MB; four wheel pivots, factory lamps and indicators.`);
