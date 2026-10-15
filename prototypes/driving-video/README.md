# Driving theory video — prototype (Bilet 1, savol 12)

A proof of concept: one animated explanation video for one real exam question, rendered locally with
[Remotion](https://www.remotion.dev/) (React → MP4). It is fully separate from the Django site: nothing outside
this folder is read at runtime except the source image (copied by `npm run prepare-assets`).

Output: `output/bilet-1-savol-12.mp4` — 1920×1080, 30 fps, H.264, 39 s, **no audio** (Uzbek subtitles only).

## The question

| | |
|---|---|
| Database | `avto_question.id = 209`, category «Bilet 1» (id 14), topic «Tartibga soluvchining ishoralari» |
| Text | «Harakatlanish taqiqlangan:» |
| Image | `core/media/questions/images/bilet-1-5.webp` (945×530) |
| Correct answer | **«Ko‘k, yashil va oq avtomobillarga.»** — `avto_answer.id = 660`, `togri = 1` |
| Wrong | «Oq, ko‘k va sariq…» (661), «Qizil va oq…» (659) |

«Savol 12» is the position the question had in one shuffled Shablon session (sessions use `order_by("?")`).
In the bilet's fixed order it is question 5. The label is a single field (`facts.questionLabel`).

## Verified rule

**Yo‘l harakati qoidalari, 38-band** — Vazirlar Mahkamasining 2022-yil 12-apreldagi 172-son qarori
(in force since 01.05.2022; <https://lex.uz/uz/docs/-5953883>). Arms extended sideways or lowered:

> chap va o‘ng yon tomonidan tramvayga to‘g‘riga, relssiz transport vositalariga to‘g‘riga va o‘ngga
> harakatlanishga, piyodalarga qatnov qismini kesib o‘tishga ruxsat beriladi; old va orqa tomonidan barcha
> transport vositalari va piyodalarning harakatlanishi taqiqlanadi.

The older rules (VM 370, 2015) had the same wording in paragraph 38 but are no longer in force.

## Reading the picture (checked frame by frame)

| Vehicle | Position relative to the controller | Result |
|---|---|---|
| Oq (white) | front — he faces it | prohibited |
| Yashil (green) | back | prohibited |
| Ko‘k (blue) | side (left road), **front-left turn indicator on** → left turn | prohibited (side traffic: straight/right only) |
| Qizil (red) | side (left road), no indicator | may go straight or right |
| Sariq (yellow) | side (right road), no indicator | may go straight or right |

This matches the database answer.

## Storyboard (frames at 30 fps)

| Chapter | Time | What happens |
|---|---|---|
| Savol | 0–3.7 s | Full-bleed picture, slow push-in, ticket chip + question title |
| Ishora | 3.7–13.2 s | Picture settles into the lesson layout; zoom on the controller; side (green) and front/back (red) direction arrows; top-down gesture diagram + rule cards |
| Avtomobillar | 13.2–28 s | Spotlight on each car in turn: white, green (STOP), blue (turn indicator pulse → crossed left-turn arrow, STOP), red + yellow (green straight/right arrows) — checklist fills on the right |
| Javob | 28–35 s | The three answer choices; each wrong one gets the vehicle that breaks it, then the correct one turns green |
| Xulosa | 35–39 s | Correct answer, YHQ 38-band card, left-turn reminder, fade to wordmark |

Vehicles are never moved. The picture is a single low-resolution render, so cut-outs would look fake; the
video animates highlights, perspective-aligned arrows (drawn along the real lanes) and labels instead.

## Files

```
question-1-12.json    all data: facts (verified) · visual (overlay geometry in image px) · timeline · narration
narration-uz.txt      narration script (generated from the cues)
subtitles-uz.srt      subtitles with timings (generated from the cues)
src/                  Remotion composition
  DrivingQuestionVideo.tsx   layout, panel switching, intro → lesson transition
  components/Stage.tsx       picture + camera, spotlight, rings, arrows, labels
  components/Panels.tsx      gesture diagram, vehicle checklist, answers, summary
  components/Chrome.tsx      header, intro title, subtitles, chapter bar
scripts/stills.mjs    renders review stills
scripts/subtitles.mjs regenerates the .srt and .txt from the JSON
```

## Commands

```bash
cd prototypes/driving-video
npm install
npm run prepare-assets          # copies + 2× lanczos upscale of the question image into public/
npm run render                  # → output/bilet-1-savol-12.mp4
npm run studio                  # live preview / scrubbing in the browser
node scripts/stills.mjs /tmp/stills 150 450 1000   # single frames for review
node scripts/subtitles.mjs      # after editing cues
```

Rendering takes about 40 s on an M2. The first render downloads Chrome Headless Shell (~170 MB).

## Adding narration

No reliable offline Uzbek text-to-speech was available (macOS has no Uzbek voice; nothing is installed for it),
so the video has no audio rather than a wrong-language voice. To add a recorded voice:

1. Record `narration-uz.txt`, save as `public/narration-uz.wav` (or .mp3).
2. Set `"narration": {"audioPath": "narration-uz.wav"}` in the JSON.
3. Retime `timeline.cues`/`events` to the recording, run `node scripts/subtitles.mjs`, then `npm run render`.

Free online voices (e.g. Microsoft's uz-UZ neural voices via `edge-tts`) would work without an API key, but
they send the text to an outside service; not used here.

## Limitations

- The source image is 945×530; it is upscaled ~1.3–1.8× on screen, so it is a little soft. A higher-resolution
  render of the scene would improve every frame.
- Overlay coordinates (cars, arrows, label spots) are hand-placed per question in `visual`. Bulk generation
  would need them produced per image (by a person or a vision model) and then reviewed.
- Arrows show the *permitted directions*, not exact driving paths; the blue car's left-turn arrow is kept short
  so it never covers the controller's signal.
- Fonts load from Google Fonts at render time (needs internet).
- Remotion is free for individuals and companies of up to 3 people; larger companies need a company licence.
- The `Question.video` field already exists in the Django model; nothing is connected to it yet.
