# Driving Universe

The public course collection is a separate Three.js scene. It does not import or alter the opening driving experience.

Build from the repository root:

```
frontend/drive/node_modules/.bin/esbuild frontend/drive/universe/universe.js --bundle --format=esm --target=es2020 --minify --legal-comments=eof --outfile=core/static/site/universe/universe.js
```

Django supplies all course names, durations, features, prices and enrollment category values through `core/templates/site/atlas/courses.html`. Scene composition lives in `universe.js`; its `definitions` map controls the camera for each category. Styles are scoped in `core/static/site/universe/universe.css`.

The Malibu is a live GLB. Ducati and Isuzu use licensed, transparent, multi-angle model renders selected by camera azimuth, composited into the same Three.js world. They are deliberately not described as downloadable GLBs: the publishers' protected meshes were not extracted. Attribution and asset modifications are documented in `core/static/site/universe/SOURCES.txt` and in the scene's visible credits.

Rendering happens on demand, with animated frames only during camera travel. The renderer pauses outside the viewport or when the tab is hidden. Mobile caps pixel density and disables shadow maps. Reduced motion disables the scroll entrance and camera transitions. The enrollment links retain the site's existing `data-category` behavior.

A reversible snapshot of the previous section, scripts and containing styles was created before implementation:
`/private/tmp/avto-driving-universe-checkpoint/before.tar.gz`
The accompanying `working-tree.patch` preserves the pre-existing tracked workspace changes.

Browser screenshots, transition samples and the latest acceptance report are in `design-review/universe/`.
