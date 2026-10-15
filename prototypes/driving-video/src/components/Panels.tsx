import React from 'react';
import {appear, C, during, fontFamily, PANEL} from '../theme';
import type {QuestionVideoData} from '../types';

type Props = {data: QuestionVideoData; frame: number};

const Card: React.FC<{t: number; children: React.ReactNode; style?: React.CSSProperties}> = ({t, children, style}) => (
  <div
    style={{
      opacity: t,
      transform: `translateY(${(1 - t) * 18}px)`,
      background: 'rgba(255,255,255,0.035)',
      border: `1px solid ${C.line}`,
      borderRadius: 18,
      padding: '20px 24px',
      ...style,
    }}
  >
    {children}
  </div>
);

const Eyebrow: React.FC<{children: React.ReactNode; color?: string}> = ({children, color = C.yellow}) => (
  <div style={{fontSize: 17, fontWeight: 700, letterSpacing: 2.2, textTransform: 'uppercase', color}}>{children}</div>
);

const PanelShell: React.FC<{t: number; eyebrow: string; title: string; children: React.ReactNode}> = ({t, eyebrow, title, children}) => (
  <div
    style={{
      position: 'absolute',
      left: PANEL.x,
      top: PANEL.y,
      width: PANEL.w,
      height: PANEL.h,
      opacity: t,
      transform: `translateX(${(1 - t) * 24}px)`,
      fontFamily,
      color: C.text,
      display: 'flex',
      flexDirection: 'column',
      gap: 18,
    }}
  >
    <div>
      <Eyebrow>{eyebrow}</Eyebrow>
      <div style={{fontSize: 36, fontWeight: 800, marginTop: 8, letterSpacing: -0.5}}>{title}</div>
    </div>
    {children}
  </div>
);

/** Top-down sketch of the gesture, oriented like the picture: chest toward the bottom (white car). */
const GestureDiagram: React.FC<{sideT: number; fbT: number}> = ({sideT, fbT}) => {
  const zone = (d: string, color: string, t: number) => <path d={d} fill={color} opacity={0.18 * t} />;
  return (
    <svg width={528} height={270} viewBox="-264 -150 528 300">
      {/* four approach zones */}
      {zone('M -264 -60 L -70 -60 L -70 60 L -264 60 Z', C.green, sideT)}
      {zone('M 264 -60 L 70 -60 L 70 60 L 264 60 Z', C.green, sideT)}
      {zone('M -60 -150 L 60 -150 L 60 -70 L -60 -70 Z', C.red, fbT)}
      {zone('M -60 150 L 60 150 L 60 70 L -60 70 Z', C.red, fbT)}
      <rect x={-264} y={-60} width={528} height={120} fill="none" stroke={C.line} strokeWidth={1.5} />
      <rect x={-60} y={-150} width={120} height={300} fill="none" stroke={C.line} strokeWidth={1.5} />

      {/* side traffic: straight and right allowed */}
      <g opacity={sideT}>
        <path d="M -250 30 L -110 30" stroke={C.green} strokeWidth={6} strokeLinecap="round" />
        <path d="M -118 20 L -102 30 L -118 40" fill="none" stroke={C.green} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
        <path d="M -250 30 Q -170 30 -170 60 L -170 120" fill="none" stroke={C.green} strokeWidth={6} strokeLinecap="round" />
        <path d="M -180 112 L -170 128 L -160 112" fill="none" stroke={C.green} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
        <path d="M 250 -30 L 110 -30" stroke={C.green} strokeWidth={6} strokeLinecap="round" />
        <path d="M 118 -40 L 102 -30 L 118 -20" fill="none" stroke={C.green} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
        <path d="M 250 -30 Q 170 -30 170 -60 L 170 -120" fill="none" stroke={C.green} strokeWidth={6} strokeLinecap="round" />
        <path d="M 160 -112 L 170 -128 L 180 -112" fill="none" stroke={C.green} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
      </g>

      {/* front / back: stop */}
      <g opacity={fbT} fontFamily={fontFamily}>
        {[-112, 112].map((y) => (
          <g key={y} transform={`translate(0 ${y})`}>
            <polygon points="-10,-24 10,-24 24,-10 24,10 10,24 -10,24 -24,10 -24,-10" fill={C.red} stroke="#fff" strokeWidth={2} />
            <text y={4.5} textAnchor="middle" fontSize={12.5} fontWeight={800} fill="#fff">STOP</text>
          </g>
        ))}
        <text x={74} y={-120} fontSize={17} fontWeight={700} fill={C.text}>ORQA</text>
        <text x={74} y={128} fontSize={17} fontWeight={700} fill={C.text}>OLD (ko‘krak)</text>
      </g>

      {/* controller seen from above */}
      <g>
        <rect x={-62} y={-6} width={124} height={12} rx={6} fill={C.yellow} />
        <ellipse cx={0} cy={0} rx={30} ry={18} fill="#1E3A8A" stroke={C.yellow} strokeWidth={2.5} />
        <circle cx={0} cy={0} r={11} fill="#0F1A2E" stroke="#fff" strokeWidth={2} />
        <path d="M -8 24 L 0 34 L 8 24" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
};

export const SignalPanel: React.FC<Props & {t: number}> = ({data, frame, t}) => {
  const e = data.timeline.events;
  const sideT = appear(frame, e.sideArrows);
  const fbT = appear(frame, e.frontBackArrows);
  return (
    <PanelShell t={t} eyebrow={`Ishora · ${data.facts.rule.reference}`} title={data.facts.controller.gesture}>
      <Card t={appear(frame, e.controllerRing + 10)} style={{padding: '12px 0', display: 'flex', justifyContent: 'center'}}>
        <GestureDiagram sideT={sideT} fbT={fbT} />
      </Card>
      <Card t={sideT} style={{display: 'flex', gap: 16, alignItems: 'center', borderColor: 'rgba(34,197,94,0.35)'}}>
        <Dot color={C.green} />
        <div style={{fontSize: 24, lineHeight: 1.3}}>
          <b>Yon tomonidan:</b> to‘g‘riga va o‘ngga — <span style={{color: C.green, fontWeight: 700}}>ruxsat</span>
        </div>
      </Card>
      <Card t={fbT} style={{display: 'flex', gap: 16, alignItems: 'center', borderColor: 'rgba(239,68,68,0.35)'}}>
        <Dot color={C.red} />
        <div style={{fontSize: 24, lineHeight: 1.3}}>
          <b>Old va orqa tomonidan:</b> <span style={{color: C.red, fontWeight: 700}}>taqiqlanadi</span>
        </div>
      </Card>
    </PanelShell>
  );
};

const Dot: React.FC<{color: string}> = ({color}) => (
  <div style={{width: 14, height: 14, borderRadius: 7, background: color, flexShrink: 0, boxShadow: `0 0 0 5px ${color}33`}} />
);

const SWATCH: Record<string, string> = {white: '#F1F5F9', green: '#16A34A', blue: '#2563EB', red: '#DC2626', yellow: '#EAB308'};

export const VehiclesPanel: React.FC<Props & {t: number}> = ({data, frame, t}) => {
  const e = data.timeline.events;
  const at: Record<string, number> = {white: e.white, green: e.green, blue: e.blueSignal, red: e.permitted, yellow: e.permitted + 6};
  const statusAt: Record<string, number> = {...at, blue: e.blueLeft};
  return (
    <PanelShell t={t} eyebrow="Tahlil" title="Har bir avtomobil">
      <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
        {data.facts.vehicles.map((veh) => {
          const rowT = appear(frame, at[veh.id] + 6);
          const statusT = appear(frame, statusAt[veh.id] + 10);
          const stop = veh.status === 'prohibited';
          const color = stop ? C.red : C.green;
          const active = during(frame, at[veh.id], veh.id === 'blue' ? e.permitted : veh.id === 'white' ? e.green : veh.id === 'green' ? e.blueSignal : e.answers);
          return (
            <Card
              key={veh.id}
              t={rowT}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 18,
                padding: '15px 20px',
                borderColor: statusT > 0.5 ? `${color}${active > 0.5 ? 'AA' : '55'}` : C.line,
                background: active > 0.5 ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.035)',
              }}
            >
              <div style={{width: 40, height: 40, borderRadius: 12, background: SWATCH[veh.id], flexShrink: 0, boxShadow: 'inset 0 -6px 0 rgba(0,0,0,0.18)'}} />
              <div style={{flex: 1, minWidth: 0}}>
                <div style={{fontSize: 25, fontWeight: 750}}>{veh.name}</div>
                <div style={{fontSize: 18, color: C.muted, marginTop: 2}}>{veh.position}</div>
              </div>
              <div
                style={{
                  opacity: statusT,
                  transform: `scale(${0.85 + 0.15 * statusT})`,
                  padding: '8px 14px',
                  borderRadius: 999,
                  background: stop ? C.redSoft : C.greenSoft,
                  color,
                  fontSize: 17,
                  fontWeight: 800,
                  letterSpacing: 1,
                }}
              >
                {stop ? 'TO‘XTAYDI' : 'YURA OLADI'}
              </div>
            </Card>
          );
        })}
      </div>
    </PanelShell>
  );
};

export const AnswersPanel: React.FC<Props & {t: number}> = ({data, frame, t}) => {
  const e = data.timeline.events;
  const wrongs = data.facts.answerChoices.filter((a) => !a.correct);
  const verdictAt = (dbId: number, correct: boolean) => (correct ? e.correct : wrongs[0].dbId === dbId ? e.wrongA : e.wrongB);
  return (
    <PanelShell t={t} eyebrow="Javoblar" title={data.facts.questionText}>
      <div style={{display: 'flex', flexDirection: 'column', gap: 14}}>
        {data.facts.answerChoices.map((a, i) => {
          const vt = appear(frame, verdictAt(a.dbId, a.correct));
          const color = a.correct ? C.green : C.red;
          return (
            <Card
              key={a.dbId}
              t={appear(frame, e.answers + i * 5)}
              style={{
                padding: '18px 22px',
                borderColor: vt > 0.3 ? color : C.line,
                borderWidth: vt > 0.3 ? 2 : 1,
                background: vt > 0.3 ? (a.correct ? C.greenSoft : 'rgba(239,68,68,0.07)') : 'rgba(255,255,255,0.035)',
                boxShadow: a.correct && vt > 0 ? `0 0 ${36 * vt}px rgba(34,197,94,${0.28 * vt})` : undefined,
              }}
            >
              <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
                <div
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: 19,
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: vt > 0.3 ? color : 'rgba(255,255,255,0.08)',
                    fontSize: 22,
                    fontWeight: 800,
                    color: '#fff',
                  }}
                >
                  {vt > 0.3 ? (a.correct ? '✓' : '✕') : ''}
                </div>
                <div style={{fontSize: 26, fontWeight: 650, lineHeight: 1.25, opacity: !a.correct && vt > 0.3 ? 0.75 : 1}}>{a.text}</div>
              </div>
              {(a.correct || a.whyWrong) && (
                <div style={{opacity: vt, marginLeft: 54, marginTop: 8 * vt, maxHeight: 40 * vt, overflow: 'hidden', fontSize: 19, color, fontWeight: 650}}>
                  {a.correct ? 'To‘g‘ri javob' : a.whyWrong}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </PanelShell>
  );
};

export const SummaryPanel: React.FC<Props & {t: number}> = ({data, frame, t}) => {
  const e = data.timeline.events;
  const {facts} = data;
  return (
    <PanelShell t={t} eyebrow="Xulosa" title="Yodda tuting">
      <Card t={appear(frame, e.summary + 4)} style={{borderColor: 'rgba(34,197,94,0.6)', background: C.greenSoft, padding: '22px 26px'}}>
        <Eyebrow color={C.green}>To‘g‘ri javob</Eyebrow>
        <div style={{fontSize: 32, fontWeight: 800, marginTop: 10, lineHeight: 1.2}}>{facts.correctAnswerShort}</div>
      </Card>
      <Card t={appear(frame, e.summary + 14)} style={{borderColor: 'rgba(250,204,21,0.45)', background: C.yellowSoft, padding: '22px 26px'}}>
        <Eyebrow>Qoida: {facts.rule.reference}</Eyebrow>
        <div style={{fontSize: 23, marginTop: 12, lineHeight: 1.4}}>
          Qo‘llar yon tomonga uzatilganda: yon tomondan <b style={{color: C.green}}>to‘g‘riga va o‘ngga</b> mumkin, old va orqa
          tomondan <b style={{color: C.red}}>taqiqlanadi</b>.
        </div>
        <div style={{fontSize: 17, color: C.muted, marginTop: 14}}>{facts.rule.document}</div>
      </Card>
      <Card t={appear(frame, e.summary + 24)} style={{borderColor: 'rgba(239,68,68,0.4)', display: 'flex', gap: 16, alignItems: 'center'}}>
        <Dot color={C.red} />
        <div style={{fontSize: 23, lineHeight: 1.35}}>
          <b>Diqqat:</b> yon tomondan ham <b style={{color: C.red}}>chapga burilish</b> mumkin emas — faqat to‘g‘riga va o‘ngga.
        </div>
      </Card>
    </PanelShell>
  );
};
