export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds % 60));
  const m = Math.floor((seconds / 60) % 60);
  const h = Math.floor(seconds / 3600);
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m);
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function formatRange(start: number, end: number): string {
  return `${formatDuration(start)} → ${formatDuration(end)} (${(end - start).toFixed(1)}s)`;
}

export function clampPct(p: number): number {
  if (!Number.isFinite(p)) return 0;
  return Math.max(0, Math.min(100, p));
}
