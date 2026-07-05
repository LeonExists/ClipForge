import type { JobSnapshot, JobStatus, Stage } from '../types';

export interface ClipProgress {
  clipId: string;
  jobId?: string;
  title?: string;
  status: JobStatus;
  currentStage: Stage;
  pct: number;
  message?: string;
  error?: string | null;
  outputReady: boolean;
  ts: number;
}

export interface ProgressState {
  byClip: Map<string, ClipProgress>;
  order: string[];
}

export const initProgress = (): ProgressState => ({ byClip: new Map(), order: [] });

export type Action = { type: 'event'; event: JobSnapshot } | { type: 'reset' };

const STAGE_INDEX: Record<Stage, number> = {
  download: 0,
  transcribe: 1,
  caption: 2,
  render: 3,
  done: 4,
};

const clampPct = (p: number) => Math.max(0, Math.min(100, p || 0));

export function progressReducer(state: ProgressState, a: Action): ProgressState {
  if (a.type === 'reset') return initProgress();
  const e = a.event;
  const prev = state.byClip.get(e.clipId);
  if (prev && e.ts < prev.ts) return state; // out-of-order dedupe

  const next: ClipProgress = {
    clipId: e.clipId,
    jobId: e.jobId,
    title: e.title ?? prev?.title,
    status: e.status,
    currentStage: e.stage,
    pct: e.status === 'done' ? 100 : clampPct(e.pct),
    message: e.message,
    error: e.error,
    outputReady: e.status === 'done',
    ts: e.ts,
  };
  const byClip = new Map(state.byClip);
  byClip.set(e.clipId, next);
  const order = prev ? state.order : [...state.order, e.clipId];
  return { byClip, order };
}

// Per-stepper-node state for a ProgressCard.
export function stageState(cp: ClipProgress, stage: Stage): 'pending' | 'active' | 'complete' | 'error' {
  const cur = STAGE_INDEX[cp.currentStage];
  const s = STAGE_INDEX[stage];
  if (cp.status === 'done') return 'complete';
  if (cp.status === 'error' && s === cur) return 'error';
  if (s < cur) return 'complete';
  if (s === cur) return 'active';
  return 'pending';
}
