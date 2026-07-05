// Shared types mirroring the backend contract.

export interface Clip {
  id: string;
  videoId: string;
  url: string;
  title: string;
  start: number;
  end: number;
  createdAt?: string;
  note?: string;
}

export type ReframeMode = 'crop' | 'blur_pad';
export type WhisperModel =
  | 'tiny' | 'tiny.en' | 'base' | 'base.en'
  | 'small' | 'small.en' | 'medium' | 'medium.en' | 'large-v3';

export interface JobConfig {
  reframe_mode: ReframeMode;
  whisper_model: WhisperModel;
  precise_cuts: boolean;
  caption_preset: string;
}

export const DEFAULT_CONFIG: JobConfig = {
  reframe_mode: 'crop',
  whisper_model: 'small.en',
  precise_cuts: true,
  caption_preset: 'shorts_bold',
};

// Pipeline stages in execution order (matches backend Stage enum + UI stepper).
export type Stage = 'download' | 'transcribe' | 'caption' | 'render' | 'done';
export const STAGES: readonly Stage[] = ['download', 'transcribe', 'caption', 'render', 'done'];
export type JobStatus = 'pending' | 'running' | 'done' | 'error';

export interface RunCreated {
  runId: string;
  jobs: { jobId: string; clipId: string }[];
}

export interface JobSnapshot {
  runId: string;
  clipId: string;
  jobId: string;
  title?: string;
  stage: Stage;
  pct: number;
  status: JobStatus;
  message?: string;
  error?: string | null;
  ts: number;
}

export interface RunSnapshot {
  runId: string;
  status: string;
  jobs: JobSnapshot[];
}

export interface Preset {
  id: string;
  label: string;
  font?: string;
  animation?: string;
}
