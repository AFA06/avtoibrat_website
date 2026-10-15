import React from 'react';
import {AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {ChapterBar, Header, IntroTitle, Subtitles} from './components/Chrome';
import {AnswersPanel, SignalPanel, SummaryPanel, VehiclesPanel} from './components/Panels';
import {Stage} from './components/Stage';
import {C, during, fontFamily, STAGE} from './theme';
import type {QuestionVideoData} from './types';

export const DrivingQuestionVideo: React.FC<{data: QuestionVideoData}> = ({data}) => {
  const frame = useCurrentFrame();
  const {timeline} = data;
  const e = timeline.events;
  const ch = Object.fromEntries(timeline.chapters.map((c) => [c.id, c]));

  // Full-bleed picture during the intro, then it settles into the lesson layout.
  const [l0, l1] = timeline.layoutAt;
  const k = interpolate(frame, [l0, l1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  const rect = {
    x: STAGE.x * k,
    y: STAGE.y * k,
    w: 1920 + (STAGE.w - 1920) * k,
    h: 1080 + (STAGE.h - 1080) * k,
    r: STAGE.r * k,
  };

  const end = interpolate(frame, [e.fadeOut, timeline.durationInFrames - 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(120% 90% at 30% 20%, ${C.bg2} 0%, ${C.bg} 60%)`,
        fontFamily,
      }}
    >
      {data.narration.audioPath && <Audio src={staticFile(data.narration.audioPath)} />}

      <Stage data={data} frame={frame} rect={rect} />
      <IntroTitle data={data} frame={frame} t={1 - interpolate(frame, [l0 - 14, l0 + 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />

      <Header data={data} frame={frame} t={during(frame, l1 - 8, 99999, 16)} />
      <SignalPanel data={data} frame={frame} t={during(frame, ch.signal.from + 12, ch.signal.to + 4, 14)} />
      <VehiclesPanel data={data} frame={frame} t={during(frame, ch.vehicles.from + 4, ch.vehicles.to + 2, 14)} />
      <AnswersPanel data={data} frame={frame} t={during(frame, ch.answer.from + 2, ch.answer.to + 2, 14)} />
      <SummaryPanel data={data} frame={frame} t={during(frame, ch.summary.from + 2, 99999, 14)} />
      <ChapterBar data={data} frame={frame} t={during(frame, l1 - 8, 99999, 16)} />
      <Subtitles data={data} frame={frame} />

      <AbsoluteFill style={{background: C.bg, opacity: end * 0.9, pointerEvents: 'none'}} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: end, color: C.text, fontSize: 54, fontWeight: 800, letterSpacing: 4}}>
        <div>
          AVTO<span style={{color: C.yellow}}>IBRAT</span>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
