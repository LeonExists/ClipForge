import { describe, expect, it } from 'vitest';
import { clipStats, groupByVideoId } from './grouping';
import type { Clip } from '../types';

const C = (id: string, videoId: string): Clip => ({
  id,
  videoId,
  url: `https://y/${videoId}`,
  title: 't',
  start: 0,
  end: 1,
});

describe('groupByVideoId', () => {
  it('preserves first-seen order', () => {
    const g = groupByVideoId([C('1', 'A'), C('2', 'B'), C('3', 'A')]);
    expect(g.map((x) => x.videoId)).toEqual(['A', 'B']);
    expect(g[0].clips).toHaveLength(2);
  });
});

describe('clipStats', () => {
  it('counts clips and sources', () => {
    const s = clipStats([C('1', 'A'), C('2', 'A'), C('3', 'B')]);
    expect(s.clipCount).toBe(3);
    expect(s.videoCount).toBe(2);
    expect(s.hasSharedSources).toBe(true);
  });

  it('no shared sources when all distinct', () => {
    const s = clipStats([C('1', 'A'), C('2', 'B')]);
    expect(s.hasSharedSources).toBe(false);
  });
});
