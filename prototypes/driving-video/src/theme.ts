import {loadFont} from '@remotion/google-fonts/Inter';
import {Easing, interpolate} from 'remotion';

export const {fontFamily} = loadFont('normal', {
  weights: ['400', '500', '600', '700', '800'],
  subsets: ['latin', 'latin-ext'],
});

export const C = {
  bg: '#0A1120',
  bg2: '#0F1A2E',
  panel: 'rgba(17, 27, 46, 0.92)',
  line: 'rgba(148, 163, 184, 0.18)',
  text: '#F4F7FB',
  muted: '#93A3BA',
  green: '#22C55E',
  greenSoft: 'rgba(34, 197, 94, 0.16)',
  red: '#EF4444',
  redSoft: 'rgba(239, 68, 68, 0.16)',
  yellow: '#FACC15',
  yellowSoft: 'rgba(250, 204, 21, 0.14)',
  amber: '#F59E0B',
};

export const STAGE = {x: 56, y: 150, w: 1200, h: 673, r: 22};
export const PANEL = {x: 1288, y: 150, w: 576, h: 673};

/** 0→1 from `at` over `dur` frames, eased. */
export const appear = (frame: number, at: number, dur = 16) =>
  interpolate(frame, [at, at + dur], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

/** Visible between `from` and `to`, with fades at both ends. */
export const during = (frame: number, from: number, to: number, fade = 10) =>
  Math.min(appear(frame, from, fade), 1 - appear(frame, to - fade, fade));
