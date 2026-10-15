import type question from '../question-1-12.json';

export type QuestionVideoData = typeof question;
export type VehicleId = keyof QuestionVideoData['visual']['vehicles'];
export type Point = [number, number];

/** Where the image sits on screen and how it is zoomed — shared by the image, SVG overlays and HTML labels. */
export type View = {
  /** image px → screen px */
  scale: number;
  tx: number;
  ty: number;
};

export const toScreen = (view: View, [x, y]: Point): Point => [x * view.scale + view.tx, y * view.scale + view.ty];
