import type { Clip } from '../types';

export interface VideoGroup {
  videoId: string;
  clips: Clip[];
}

export function groupByVideoId(clips: Clip[]): VideoGroup[] {
  const order: string[] = [];
  const m = new Map<string, Clip[]>();
  for (const c of clips) {
    if (!m.has(c.videoId)) {
      m.set(c.videoId, []);
      order.push(c.videoId);
    }
    m.get(c.videoId)!.push(c);
  }
  return order.map((v) => ({ videoId: v, clips: m.get(v)! }));
}

export interface ClipStats {
  clipCount: number;
  videoCount: number;
  hasSharedSources: boolean;
}

export function clipStats(clips: Clip[]): ClipStats {
  const g = groupByVideoId(clips);
  return {
    clipCount: clips.length,
    videoCount: g.length,
    hasSharedSources: g.some((x) => x.clips.length > 1),
  };
}
