import { describe, expect, it } from 'vitest';
import { initProgress, progressReducer, stageState } from './progressReducer';
import type { JobSnapshot } from '../types';

const ev = (over: Partial<JobSnapshot>): JobSnapshot => ({
  runId: 'r',
  clipId: 'c1',
  jobId: 'c1',
  stage: 'download',
  pct: 0,
  status: 'running',
  ts: 1,
  ...over,
});

describe('progressReducer', () => {
  it('adds a new clip to order', () => {
    const s = progressReducer(initProgress(), { type: 'event', event: ev({}) });
    expect(s.order).toEqual(['c1']);
    expect(s.byClip.get('c1')?.currentStage).toBe('download');
  });

  it('advances stage and pct', () => {
    let s = progressReducer(initProgress(), { type: 'event', event: ev({ ts: 1 }) });
    s = progressReducer(s, { type: 'event', event: ev({ stage: 'render', pct: 50, ts: 2 }) });
    expect(s.byClip.get('c1')?.currentStage).toBe('render');
    expect(s.byClip.get('c1')?.pct).toBe(50);
  });

  it('ignores out-of-order (older ts) events', () => {
    let s = progressReducer(initProgress(), { type: 'event', event: ev({ stage: 'caption', ts: 5 }) });
    s = progressReducer(s, { type: 'event', event: ev({ stage: 'download', ts: 2 }) });
    expect(s.byClip.get('c1')?.currentStage).toBe('caption');
  });

  it('done sets outputReady + 100%', () => {
    const s = progressReducer(initProgress(), { type: 'event', event: ev({ status: 'done', stage: 'done', ts: 3 }) });
    const c = s.byClip.get('c1')!;
    expect(c.outputReady).toBe(true);
    expect(c.pct).toBe(100);
  });

  it('error stores the error', () => {
    const s = progressReducer(initProgress(), { type: 'event', event: ev({ status: 'error', error: 'boom', ts: 3 }) });
    expect(s.byClip.get('c1')?.error).toBe('boom');
  });

  it('reset clears state', () => {
    let s = progressReducer(initProgress(), { type: 'event', event: ev({}) });
    s = progressReducer(s, { type: 'reset' });
    expect(s.order).toHaveLength(0);
  });
});

describe('stageState', () => {
  const base = {
    clipId: 'c1',
    status: 'running' as const,
    currentStage: 'caption' as const,
    pct: 20,
    outputReady: false,
    ts: 1,
  };

  it('marks earlier stages complete, current active, later pending', () => {
    expect(stageState(base, 'download')).toBe('complete');
    expect(stageState(base, 'caption')).toBe('active');
    expect(stageState(base, 'render')).toBe('pending');
  });

  it('all complete when done', () => {
    expect(stageState({ ...base, status: 'done', currentStage: 'done' }, 'download')).toBe('complete');
    expect(stageState({ ...base, status: 'done', currentStage: 'done' }, 'render')).toBe('complete');
  });

  it('error only on the current stage', () => {
    const errored = { ...base, status: 'error' as const, currentStage: 'render' as const };
    expect(stageState(errored, 'render')).toBe('error');
    expect(stageState(errored, 'download')).toBe('complete');
  });
});
