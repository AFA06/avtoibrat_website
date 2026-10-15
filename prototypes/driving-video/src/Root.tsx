import React from 'react';
import {Composition} from 'remotion';
import question from '../question-1-12.json';
import {DrivingQuestionVideo} from './DrivingQuestionVideo';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="DrivingQuestionVideo"
    component={DrivingQuestionVideo}
    durationInFrames={question.timeline.durationInFrames}
    fps={question.timeline.fps}
    width={1920}
    height={1080}
    defaultProps={{data: question}}
  />
);
