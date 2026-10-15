// Renders review stills: node scripts/stills.mjs <outDir> <frame> [frame...]
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'node:path';

const [outDir, ...frames] = process.argv.slice(2);
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'DrivingQuestionVideo'});
for (const f of frames.map(Number)) {
  const output = path.join(outDir, `frame-${String(f).padStart(4, '0')}.png`);
  await renderStill({serveUrl, composition, frame: f, output});
  console.log(output);
}
