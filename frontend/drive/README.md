# Avtoibrat driving film

The homepage loads the prebuilt module and GLB from Django static files. Node is needed only to change the film. From this directory run `npm ci`, `npm run car` after editing the coachwork, then `npm run build`. Deployments can use the repository's normal collectstatic step.

- `build-car.mjs` prepares the owner-supplied detailed Chevrolet Gentra (`node build-car.mjs /path/to/gentra.glb`), normalizes it to 4.515 metres, batches body geometry, tunes black paint/glass/alloy/rubber and exports four steering/spinning wheel pivots plus independent factory indicator and brake lenses. The original download remains outside the tracked build output.
- `road.js` samples the spline and builds pavement, lines and a repeatable asphalt texture.
- `districts.js` builds the arcades, glazed façades, landscaping, crossing, school court and foothills.
- `world.js` maps normalized scroll progress to distance, heading, steering, camera and lighting. The intersection holds vehicle distance while the light changes.
- `director.js` owns the pinned native-scroll timeline and the chapter controls.
- `experience.js` handles the renderer, dimensions, quality selection, teardown and photographic fallback.

The Gentra model was supplied by the project owner; the original download identifies Sketchfab as its export source. No new model licensing claim is made here. Buildings, road, signs, façade textures and landscape geometry were authored for this project. This is a fictional training route inspired by Tashkent. Three.js and its GLTFLoader, RoomEnvironment and geometry utilities use the MIT license included with the static bundle. The site uses its existing GSAP 3.13 and ScrollTrigger distribution. The photographic fallback retains the credits in site/atlas/SOURCES.txt.

The practice yard reuses the film's renderer. Open chapter 06 and choose **Haydab ko‘rish**. Use WASD, the arrow keys or the on-screen pedals. Escape returns to the same chapter.

For the browser evidence, run the local Django server, install Google Chrome, then run `npm ci`, `npx playwright install ffmpeg` and `node verify.cjs` from this directory. Set `PREVIEW_URL` to use another local server. The verifier records a desktop browser run, checks seven story positions in each direction on desktop and phone, and writes the screenshots, WebM and measured scene state under `design-review/drive/`.

Turn signals follow steering direction and blink every 420 ms, including when scrolling pauses. Brake lights brighten at the traffic-light stop and while slowing in the practice yard. Wheels turn at their actual axles and roll in both directions.
