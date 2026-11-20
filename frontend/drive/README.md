# Avtoibrat driving film

The homepage loads the prebuilt module and GLB from Django static files. Node is needed only to change the film. From this directory run `npm ci`, `npm run car` after editing the coachwork, then `npm run build`. Deployments can use the repository's normal collectstatic step.

- `build-car.mjs` authors the unbranded fastback and exports its coachwork, four steering/suspension pivots and four wheels as glTF binary.
- `road.js` samples the spline and builds pavement, lines and a repeatable asphalt texture.
- `districts.js` builds the arcades, glazed façades, landscaping, crossing, school court and foothills.
- `world.js` maps normalized scroll progress to distance, heading, steering, camera and lighting. The intersection holds vehicle distance while the light changes.
- `director.js` owns the pinned native-scroll timeline and the chapter controls.
- `experience.js` handles the renderer, dimensions, quality selection, teardown and photographic fallback.

The GLB, buildings, road, signs, façade textures and landscape geometry were authored for this project. No third-party vehicle model, trademark, city scan or HDR panorama is included. This is a fictional training route inspired by Tashkent. Three.js and its GLTFLoader, RoomEnvironment and geometry utilities use the MIT license included with the static bundle. The site uses its existing GSAP 3.13 and ScrollTrigger distribution. The photographic fallback retains the credits in site/atlas/SOURCES.txt.

The practice yard reuses the film's renderer. Open chapter 06 and choose **Haydab ko‘rish**. Use WASD, the arrow keys or the on-screen pedals. Escape returns to the same chapter.

For the browser evidence, run the local Django server, install Google Chrome, then run `npm ci`, `npx playwright install ffmpeg` and `node verify.cjs` from this directory. Set `PREVIEW_URL` to use another local server. The verifier records a desktop browser run, checks seven story positions in each direction on desktop and phone, and writes the screenshots, WebM and measured scene state under `design-review/drive/`.
