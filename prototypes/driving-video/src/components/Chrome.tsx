import React from 'react';
import {interpolate} from 'remotion';
import {appear, C, during, fontFamily} from '../theme';
import type {QuestionVideoData} from '../types';

type Props = {data: QuestionVideoData; frame: number};

const ticketLabel = (data: QuestionVideoData) => `Bilet ${data.facts.ticketId} — Savol ${data.facts.questionLabel}`;

export const IntroTitle: React.FC<Props & {t: number}> = ({data, frame, t}) => {
  if (t <= 0) return null;
  const chip = appear(frame, 6);
  const title = appear(frame, 16, 20);
  return (
    <div style={{position: 'absolute', inset: 0, opacity: t, fontFamily, color: C.text}}>
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(6,11,22,0.88) 0%, rgba(6,11,22,0.35) 34%, rgba(6,11,22,0) 52%)'}} />
      <div style={{position: 'absolute', left: 96, top: 84}}>
        <div
          style={{
            display: 'inline-block',
            opacity: chip,
            transform: `translateY(${(1 - chip) * 14}px)`,
            padding: '10px 22px',
            borderRadius: 999,
            border: `2px solid ${C.yellow}`,
            color: C.yellow,
            fontSize: 28,
            fontWeight: 750,
            letterSpacing: 0.5,
            background: 'rgba(6,11,22,0.5)',
          }}
        >
          {ticketLabel(data)}
        </div>
        <div style={{opacity: title, transform: `translateY(${(1 - title) * 18}px)`, fontSize: 76, fontWeight: 800, marginTop: 22, letterSpacing: -1.5}}>
          {data.facts.questionText}
        </div>
        <div style={{opacity: title, fontSize: 28, color: '#CBD5E1', marginTop: 6, fontWeight: 500}}>{data.facts.topic}</div>
      </div>
    </div>
  );
};

export const Header: React.FC<Props & {t: number}> = ({data, t}) => (
  <div
    style={{
      position: 'absolute',
      left: 56,
      right: 56,
      top: 46,
      height: 74,
      display: 'flex',
      alignItems: 'center',
      gap: 22,
      fontFamily,
      color: C.text,
      opacity: t,
      transform: `translateY(${(1 - t) * -12}px)`,
    }}
  >
    <div style={{padding: '8px 18px', borderRadius: 999, border: `2px solid ${C.yellow}`, color: C.yellow, fontSize: 22, fontWeight: 750}}>
      {ticketLabel(data)}
    </div>
    <div style={{fontSize: 38, fontWeight: 800, letterSpacing: -0.6}}>{data.facts.questionText}</div>
    <div style={{marginLeft: 'auto', textAlign: 'right'}}>
      <div style={{fontSize: 22, fontWeight: 800, letterSpacing: 2}}>
        AVTO<span style={{color: C.yellow}}>IBRAT</span>
      </div>
      <div style={{fontSize: 17, color: C.muted, marginTop: 2}}>{data.facts.topic}</div>
    </div>
  </div>
);

export const Subtitles: React.FC<Props> = ({data, frame}) => {
  const cue = data.timeline.cues.find((c) => frame >= c.from - 6 && frame < c.to);
  if (!cue) return null;
  const t = during(frame, cue.from - 6, cue.to, 7);
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: 858, display: 'flex', justifyContent: 'center', fontFamily}}>
      <div
        style={{
          opacity: t,
          transform: `translateY(${(1 - t) * 8}px)`,
          maxWidth: 1500,
          padding: '14px 30px',
          borderRadius: 16,
          background: 'rgba(6, 11, 22, 0.82)',
          border: `1px solid ${C.line}`,
          color: '#fff',
          fontSize: 38,
          fontWeight: 600,
          lineHeight: 1.3,
          textAlign: 'center',
        }}
      >
        {cue.text}
      </div>
    </div>
  );
};

export const ChapterBar: React.FC<Props & {t: number}> = ({data, frame, t}) => (
  <div style={{position: 'absolute', left: 56, right: 56, top: 990, display: 'flex', gap: 12, fontFamily, opacity: t}}>
    {data.timeline.chapters.map((ch) => {
      const p = interpolate(frame, [ch.from, ch.to], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
      const active = frame >= ch.from && frame < ch.to;
      return (
        <div key={ch.id} style={{flex: ch.to - ch.from}}>
          <div style={{height: 5, borderRadius: 3, background: 'rgba(148,163,184,0.22)', overflow: 'hidden'}}>
            <div style={{width: `${p * 100}%`, height: '100%', background: active ? C.yellow : 'rgba(250,204,21,0.55)'}} />
          </div>
          <div style={{fontSize: 18, marginTop: 10, fontWeight: active ? 700 : 500, color: active ? C.text : C.muted}}>{ch.label}</div>
        </div>
      );
    })}
  </div>
);
