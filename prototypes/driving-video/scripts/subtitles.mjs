// Writes subtitles-uz.srt and narration-uz.txt from the cues in question-1-12.json: node scripts/subtitles.mjs
import fs from 'node:fs';

const q = JSON.parse(fs.readFileSync('question-1-12.json', 'utf8'));
const {fps, cues} = q.timeline;
const ts = (frame) => {
  const ms = Math.round((frame / fps) * 1000);
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
};
fs.writeFileSync('subtitles-uz.srt', cues.map((c, i) => `${i + 1}\n${ts(c.from)} --> ${ts(c.to)}\n${c.text}\n`).join('\n'));
fs.writeFileSync(
  'narration-uz.txt',
  `# Bilet ${q.facts.ticketId} — Savol ${q.facts.questionLabel}: diktor matni (o‘zbek, lotin)\n` +
    `# Har bir qator — bitta subtitr. Vaqtlar: subtitles-uz.srt\n\n` +
    cues.map((c) => c.text).join('\n') + '\n',
);
console.log(`${cues.length} cues written`);
