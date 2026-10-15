import React from 'react';
import {Easing, Img, interpolate, staticFile} from 'remotion';
import {appear, C, during, fontFamily} from '../theme';
import type {Point, QuestionVideoData, VehicleId, View} from '../types';
import {toScreen} from '../types';

type Rect = {x: number; y: number; w: number; h: number; r: number};
type CameraKey = QuestionVideoData['timeline']['camera'][number];

const cameraAt = (frame: number, keys: CameraKey[]) => {
  if (frame <= keys[0].frame) return keys[0];
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i];
    const b = keys[i + 1];
    if (frame < b.frame) {
      const t = interpolate(frame, [a.frame, b.frame], [0, 1], {easing: Easing.inOut(Easing.cubic)});
      return {frame, x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, zoom: a.zoom + (b.zoom - a.zoom) * t};
    }
  }
  return keys[keys.length - 1];
};

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Spotlight schedule: which things stay bright while the rest of the picture is dimmed. */
type Target = VehicleId | 'controller';
const spotlights = (e: QuestionVideoData['timeline']['events']): [number, number, Target[]][] => [
  [e.controllerRing, e.directionsOut + 5, ['controller']],
  [e.white - 5, e.green - 3, ['white']],
  [e.green - 3, e.blueSignal - 3, ['green']],
  [e.blueSignal - 3, e.permitted - 3, ['blue']],
  [e.permitted - 3, e.wrongA, ['red', 'yellow']],
  [e.wrongA, e.wrongB, ['yellow', 'green']],
  [e.wrongB, e.correct, ['red']],
  [e.correct, 99999, ['blue', 'green', 'white']],
];

type Path = {from: Point; via?: Point; to: Point};
const parsePath = (d: string): Path => {
  const n = d.match(/-?\d+(\.\d+)?/g)!.map(Number);
  return n.length === 4
    ? {from: [n[0], n[1]], to: [n[2], n[3]]}
    : {from: [n[0], n[1]], via: [n[2], n[3]], to: [n[4], n[5]]};
};
const pointAt = (p: Path, t: number): Point => {
  if (!p.via) return [p.from[0] + (p.to[0] - p.from[0]) * t, p.from[1] + (p.to[1] - p.from[1]) * t];
  const u = 1 - t;
  return [
    u * u * p.from[0] + 2 * u * t * p.via[0] + t * t * p.to[0],
    u * u * p.from[1] + 2 * u * t * p.via[1] + t * t * p.to[1],
  ];
};

const Arrow: React.FC<{d: string; progress: number; color: string; width: number; crossed?: boolean; opacity?: number}> = ({
  d,
  progress,
  color,
  width,
  crossed,
  opacity = 1,
}) => {
  if (progress <= 0) return null;
  const p = parsePath(d);
  const tail = p.via ?? p.from;
  const angle = (Math.atan2(p.to[1] - tail[1], p.to[0] - tail[0]) * 180) / Math.PI;
  const head = width * 2.6;
  const headOpacity = interpolate(progress, [0.75, 1], [0, 1], {extrapolateLeft: 'clamp'});
  const mid = pointAt(p, 0.55);
  // Stop the line short of the tip so the arrowhead point stays sharp.
  return (
    <g opacity={opacity}>
      <path d={d} pathLength={1} stroke="rgba(5,10,20,0.55)" strokeWidth={width + 4} fill="none" strokeLinecap="round"
        strokeDasharray={1} strokeDashoffset={1 - progress * 0.94} />
      <path d={d} pathLength={1} stroke={color} strokeWidth={width} fill="none" strokeLinecap="round"
        strokeDasharray={1} strokeDashoffset={1 - progress * 0.94} />
      <g transform={`translate(${p.to[0]} ${p.to[1]}) rotate(${angle})`} opacity={headOpacity}>
        <path d={`M ${-head} ${-head * 0.62} L 2 0 L ${-head} ${head * 0.62} Z`} fill={color}
          stroke="rgba(5,10,20,0.55)" strokeWidth={1.6} strokeLinejoin="round" />
      </g>
      {crossed && (
        <g transform={`translate(${mid[0]} ${mid[1]}) scale(${headOpacity})`}>
          <circle r={12} fill={C.red} stroke="#fff" strokeWidth={2.4} />
          <path d="M -5 -5 L 5 5 M 5 -5 L -5 5" stroke="#fff" strokeWidth={3} strokeLinecap="round" />
        </g>
      )}
    </g>
  );
};

const Ring: React.FC<{x: number; y: number; rx: number; ry: number; color: string; t: number; frame: number; at: number}> = ({
  x, y, rx, ry, color, t, frame, at,
}) => {
  if (t <= 0) return null;
  // One soft ripple when the ring arrives; no repeated flashing.
  const ripple = interpolate(frame, [at, at + 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <g>
      <ellipse cx={x} cy={y} rx={rx * (1 + ripple * 0.35)} ry={ry * (1 + ripple * 0.35)} fill="none" stroke={color}
        strokeWidth={2} opacity={(1 - ripple) * 0.7 * t} />
      <ellipse cx={x} cy={y} rx={rx} ry={ry} fill={color} fillOpacity={0.1 * t} stroke={color} strokeWidth={2.6} opacity={t} />
    </g>
  );
};

type LabelKind = 'stop' | 'go' | 'signal' | 'neutral';
const LABEL_COLOR: Record<LabelKind, string> = {stop: C.red, go: C.green, signal: C.amber, neutral: C.yellow};

const Badge: React.FC<{kind: LabelKind}> = ({kind}) => {
  if (kind === 'stop') {
    return (
      <svg width={40} height={40} viewBox="-20 -20 40 40">
        <polygon points="-8.3,-20 8.3,-20 20,-8.3 20,8.3 8.3,20 -8.3,20 -20,8.3 -20,-8.3" fill={C.red} stroke="#fff" strokeWidth={2} />
        <text x={0} y={4} textAnchor="middle" fontSize={11.5} fontWeight={800} fill="#fff" fontFamily={fontFamily}>STOP</text>
      </svg>
    );
  }
  if (kind === 'go') {
    return (
      <svg width={34} height={34} viewBox="-17 -17 34 34">
        <circle r={16} fill={C.green} />
        <path d="M -7 0 L -2 5 L 7 -5" stroke="#fff" strokeWidth={3.4} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === 'signal') {
    return (
      <svg width={34} height={34} viewBox="-17 -17 34 34">
        <circle r={16} fill={C.amber} />
        <path d="M 6 6 L 6 -2 Q 6 -6 2 -6 L -6 -6 M -2 -10 L -6 -6 L -2 -2" stroke="#1a1204" strokeWidth={3} fill="none"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return null;
};

/** How a label sits relative to its point, so it never covers an arrowhead or runs off the stage. */
const ANCHOR = {
  center: 'translate(-50%, -50%)',
  start: 'translate(0, -50%)',
  end: 'translate(-100%, -50%)',
  before: 'translate(calc(-100% - 12px), -50%)',
  after: 'translate(12px, -50%)',
  belowBefore: 'translate(calc(-100% + 18px), 10px)',
  aboveAfter: 'translate(-18px, calc(-100% - 10px))',
};
type Anchor = keyof typeof ANCHOR;

const Label: React.FC<{view: View; at: Point; kind: LabelKind; text: string; t: number; anchor?: Anchor | string}> = ({
  view, at, kind, text, t, anchor = 'center',
}) => {
  if (t <= 0) return null;
  const [x, y] = toScreen(view, at);
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `${ANCHOR[anchor as Anchor]} translateY(${(1 - t) * 10}px) scale(${0.92 + 0.08 * t})`,
        opacity: t,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: kind === 'neutral' ? '8px 16px' : '5px 16px 5px 5px',
        borderRadius: 999,
        background: 'rgba(8, 14, 27, 0.88)',
        border: `2px solid ${LABEL_COLOR[kind]}`,
        boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
        color: C.text,
        fontFamily,
        fontSize: 22,
        fontWeight: 650,
        whiteSpace: 'nowrap',
      }}
    >
      <Badge kind={kind} />
      <span>{text}</span>
    </div>
  );
};

export const Stage: React.FC<{data: QuestionVideoData; frame: number; rect: Rect}> = ({data, frame, rect}) => {
  const {visual, timeline} = data;
  const e = timeline.events;
  const W = visual.imageWidth;
  const H = visual.imageHeight;

  const cam = cameraAt(frame, timeline.camera);
  const scale = Math.max(rect.w / W, rect.h / H) * cam.zoom;
  const view: View = {
    scale,
    tx: clamp(rect.w / 2 - cam.x * scale, rect.w - W * scale, 0),
    ty: clamp(rect.h / 2 - cam.y * scale, rect.h - H * scale, 0),
  };

  const v = visual.vehicles;
  const ctl = visual.controller;
  const dirs = visual.directions;
  const arrows = visual.arrows;

  // Dimming: on for the whole lesson after the intro, with holes over whatever is being discussed.
  const dim = 0.52 * during(frame, e.controllerRing, 99999, 14);
  const holes = spotlights(e);
  const holeOpacity = (target: Target) =>
    Math.max(0, ...holes.filter(([, , ts]) => ts.includes(target)).map(([a, b]) => during(frame, a, b, 10)));
  const holeShapes: {target: Target; x: number; y: number; rx: number; ry: number}[] = [
    {target: 'controller', x: ctl.x, y: ctl.y + 4, rx: 150, ry: 120},
    ...(Object.keys(v) as VehicleId[]).map((id) => ({target: id, x: v[id].x, y: v[id].y, rx: v[id].rx * 1.45, ry: v[id].ry * 1.5})),
  ];

  const dirsT = during(frame, e.sideArrows, e.directionsOut, 12);
  const frontBackT = during(frame, e.frontBackArrows, e.directionsOut, 12);
  const sideDraw = appear(frame, e.sideArrows, 22);
  const fbDraw = appear(frame, e.frontBackArrows, 22);

  const ring = (id: VehicleId, at: number, color: string) => (
    <Ring key={id} x={v[id].x} y={v[id].y} rx={v[id].rx} ry={v[id].ry} color={color} t={appear(frame, at)} frame={frame} at={at} />
  );

  // Permitted arrows step back once the answer is being discussed.
  const permittedOpacity = interpolate(frame, [e.summary, e.summary + 20], [1, 0.25], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const permittedDraw = (delay: number) => appear(frame, e.permitted + delay, 24);

  // Turn indicator: a gentle 1.5 Hz pulse, as a real indicator blinks.
  const signalOn = frame >= e.blueSignal;
  const blink = 0.55 + 0.45 * Math.cos(((frame - e.blueSignal) / 30) * Math.PI * 2 * 1.5);
  const signalT = during(frame, e.blueSignal, e.permitted, 10);

  return (
    <div
      style={{
        position: 'absolute',
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
        borderRadius: rect.r,
        overflow: 'hidden',
        background: C.bg2,
        boxShadow: rect.r > 0 ? `0 30px 80px rgba(0,0,0,0.45), 0 0 0 1px ${C.line}` : undefined,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: W,
          height: H,
          transformOrigin: '0 0',
          transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})`,
        }}
      >
        <Img src={staticFile(visual.image)} style={{width: W, height: H, display: 'block'}} />
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
          <defs>
            <filter id="soft" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="14" />
            </filter>
            <mask id="spot" maskUnits="userSpaceOnUse" x={-50} y={-50} width={W + 100} height={H + 100}>
              <rect x={-50} y={-50} width={W + 100} height={H + 100} fill="#fff" />
              <g filter="url(#soft)">
                {holeShapes.map((h) => (
                  <ellipse key={h.target} cx={h.x} cy={h.y} rx={h.rx} ry={h.ry} fill="#000" opacity={holeOpacity(h.target)} />
                ))}
              </g>
            </mask>
          </defs>

          {dim > 0 && <rect x={-50} y={-50} width={W + 100} height={H + 100} fill="#050A14" opacity={dim} mask="url(#spot)" />}

          {/* Controller */}
          <Ring x={ctl.x} y={ctl.y} rx={ctl.rx} ry={ctl.ry} color={C.yellow}
            t={during(frame, e.controllerRing, e.directionsOut, 14)} frame={frame} at={e.controllerRing} />
          <g opacity={dirsT}>
            <Arrow d={`M ${dirs.sideLeft.from.join(' ')} L ${dirs.sideLeft.to.join(' ')}`} progress={sideDraw} color={C.green} width={7} />
            <Arrow d={`M ${dirs.sideRight.from.join(' ')} L ${dirs.sideRight.to.join(' ')}`} progress={sideDraw} color={C.green} width={7} />
          </g>
          <g opacity={frontBackT}>
            <Arrow d={`M ${dirs.front.from.join(' ')} L ${dirs.front.to.join(' ')}`} progress={fbDraw} color={C.red} width={7} />
            <Arrow d={`M ${dirs.back.from.join(' ')} L ${dirs.back.to.join(' ')}`} progress={fbDraw} color={C.red} width={7} />
          </g>

          {/* Vehicles */}
          {ring('white', e.white, C.red)}
          {ring('green', e.green, C.red)}
          {signalOn && (
            <g opacity={signalT}>
              <circle cx={v.blue.signal[0]} cy={v.blue.signal[1]} r={13} fill="none" stroke={C.amber} strokeWidth={2.4} opacity={blink} />
              <circle cx={v.blue.signal[0]} cy={v.blue.signal[1]} r={6} fill={C.amber} opacity={blink * 0.55} />
            </g>
          )}
          {ring('blue', e.blueLeft, C.red)}
          {ring('red', e.permitted, C.green)}
          {ring('yellow', e.permitted, C.green)}

          {/* Manoeuvres */}
          <Arrow d={arrows.blueLeft.d} progress={appear(frame, e.blueLeft, 26)} color={C.red} width={6} crossed />
          <Arrow d={arrows.redStraight.d} progress={permittedDraw(0)} color={C.green} width={6} opacity={permittedOpacity} />
          <Arrow d={arrows.redRight.d} progress={permittedDraw(8)} color={C.green} width={6} opacity={permittedOpacity} />
          <Arrow d={arrows.yellowStraight.d} progress={permittedDraw(4)} color={C.green} width={6} opacity={permittedOpacity} />
          <Arrow d={arrows.yellowRight.d} progress={permittedDraw(12)} color={C.green} width={6} opacity={permittedOpacity} />
        </svg>
      </div>

      {/* Screen-space labels stay crisp and the same size whatever the zoom */}
      <Label view={view} at={dirs.sideLeft.to as Point} anchor="before" kind="go" text="Yon tomon" t={during(frame, e.sideArrows + 14, e.directionsOut, 12)} />
      <Label view={view} at={dirs.sideRight.to as Point} anchor="after" kind="go" text="Yon tomon" t={during(frame, e.sideArrows + 14, e.directionsOut, 12)} />
      <Label view={view} at={dirs.front.to as Point} anchor="belowBefore" kind="stop" text="Old tomon" t={during(frame, e.frontBackArrows + 14, e.directionsOut, 12)} />
      <Label view={view} at={dirs.back.to as Point} anchor="aboveAfter" kind="stop" text="Orqa tomon" t={during(frame, e.frontBackArrows + 14, e.directionsOut, 12)} />

      <Label view={view} at={v.white.labelAt as Point} anchor={v.white.labelAnchor} kind="stop" text="Oq · to‘xtaydi" t={appear(frame, e.white + 8)} />
      <Label view={view} at={v.green.labelAt as Point} anchor={v.green.labelAnchor} kind="stop" text="Yashil · to‘xtaydi" t={appear(frame, e.green + 8)} />
      <Label view={view} at={v.blue.labelAt as Point} anchor={v.blue.labelAnchor} kind="signal" text="Ko‘k · chapga burilish ishorasi"
        t={during(frame, e.blueSignal + 8, e.blueLeft + 4, 10)} />
      <Label view={view} at={v.blue.labelAt as Point} anchor={v.blue.labelAnchor} kind="stop" text="Ko‘k · to‘xtaydi" t={appear(frame, e.blueLeft + 4)} />
      <Label view={view} at={v.red.labelAt as Point} anchor={v.red.labelAnchor} kind="go" text="Qizil · yura oladi" t={appear(frame, e.permitted + 8)} />
      <Label view={view} at={v.yellow.labelAt as Point} anchor={v.yellow.labelAnchor} kind="go" text="Sariq · yura oladi" t={appear(frame, e.permitted + 14)} />
    </div>
  );
};
