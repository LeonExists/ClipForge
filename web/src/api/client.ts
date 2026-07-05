import type { Clip, JobConfig, Preset, RunCreated, RunSnapshot } from '../types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export async function submitRun(clips: Clip[], config: JobConfig): Promise<RunCreated> {
  const res = await fetch(`${BASE}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clips, config }),
  });
  return json<RunCreated>(res);
}

export async function fetchRunSnapshot(runId: string): Promise<RunSnapshot> {
  return json<RunSnapshot>(await fetch(`${BASE}/api/runs/${runId}`));
}

export async function fetchPresets(): Promise<Preset[]> {
  return json<Preset[]>(await fetch(`${BASE}/api/presets`));
}

export async function fetchHealth(): Promise<Record<string, boolean>> {
  return json<Record<string, boolean>>(await fetch(`${BASE}/api/health`));
}

export function outputUrl(runId: string, clipId: string, ts = 0): string {
  const bust = ts ? `?v=${ts}` : '';
  return `${BASE}/api/runs/${runId}/clips/${clipId}/file${bust}`;
}

export function zipUrl(runId: string): string {
  return `${BASE}/api/runs/${runId}/zip`;
}

export function eventsUrl(runId: string): string {
  return `${BASE}/events/${runId}`;
}
