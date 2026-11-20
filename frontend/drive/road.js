import * as T from 'three';
const V=(x,z)=>new T.Vector3(x,0,z);
export const path=new T.CatmullRomCurve3([[0,26],[0,5],[0,-22],[0,-38],[1,-47],[8,-53],[22,-54],[45,-54],[66,-62],[89,-71],[113,-68],[131,-59],[155,-59]].map(([x,z])=>V(x,z)));
path.arcLengthDivisions=1600;
export const length=path.getLength();
export function frame(u){
 const t=path.getTangentAt(u),side=new T.Vector3(-t.z,0,t.x);
 return {center:path.getPointAt(u),t,side};
}
export function at(u,offset=0){const f=frame(u);return f.center.addScaledVector(f.side,offset)}
function ribbon(scene,from,to,height,material,segments=300){
 const xyz=[],uv=[],idx=[];
 for(let i=0;i<=segments;i++){
 const u=i/segments;for(const d of [from,to]){const p=at(u,d);xyz.push(p.x,height,p.z);uv.push(d/4,length*u/4)}
 if(i){const k=i*2;idx.push(k-2,k,k-1,k-1,k,k+1)}
 }
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(xyz,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(idx);g.computeVertexNormals();
 material.side=T.DoubleSide;const m=new T.Mesh(g,material);m.receiveShadow=true;scene.add(m);
}
export function buildRoad(scene){
 const buf=new Uint8Array(128*128*4);let seed=17;
 for(let i=0;i<buf.length;i+=4){seed=(1664525*seed+1013904223)>>>0;const n=88+seed%40;buf.set([n,n,n,255],i)}
 const grain=new T.DataTexture(buf,128,128);grain.wrapS=grain.wrapT=T.RepeatWrapping;grain.generateMipmaps=true;grain.minFilter=T.LinearMipmapLinearFilter;grain.needsUpdate=true;
 ribbon(scene,-5.8,5.8,.012,new T.MeshStandardMaterial({color:0x454951,map:grain,roughness:.91}));
 const ivory=new T.MeshStandardMaterial({color:0xe5d8ad});for(const s of [-1,1])ribbon(scene,s*5.35-.055,s*5.35+.055,.028,ivory);
 const dashes=new T.InstancedMesh(new T.BoxGeometry(.105,.012,1.85),ivory,Math.floor(length/4));const o=new T.Object3D();
 for(let i=0;i<dashes.count;i++){const f=frame((i+.5)/dashes.count);o.position.copy(f.center);o.position.y=.034;o.rotation.y=Math.atan2(f.t.x,f.t.z);o.updateMatrix();dashes.setMatrixAt(i,o.matrix)}scene.add(dashes);
}
