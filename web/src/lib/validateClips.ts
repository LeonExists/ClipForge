import type { Clip } from '../types';

export interface ClipError {
  index: number | null;
  field?: string;
  code: string;
  message: string;
}

export interface ParseResult {
  ok: boolean;
  clips: Clip[];
  errors: ClipError[];
}

const REQUIRED_STR = ['id', 'videoId', 'url', 'title'] as const;
const REQUIRED_NUM = ['start', 'end'] as const;

export function parseClipsJson(text: string): ParseResult {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (e) {
    return {
      ok: false,
      clips: [],
      errors: [{ index: null, field: 'root', code: 'invalid_json', message: (e as Error).message }],
    };
  }
  return validateClips(raw);
}

export function validateClips(raw: unknown): ParseResult {
  const errors: ClipError[] = [];
  if (!Array.isArray(raw)) {
    return {
      ok: false,
      clips: [],
      errors: [{ index: null, field: 'root', code: 'not_array', message: 'Top-level JSON must be an array of clips.' }],
    };
  }

  const clips: Clip[] = [];
  const seen = new Set<string>();

  raw.forEach((item, i) => {
    if (typeof item !== 'object' || item === null) {
      errors.push({ index: i, code: 'not_object', message: `Clip ${i} must be an object.` });
      return;
    }
    const o = item as Record<string, unknown>;
    const before = errors.length;

    for (const f of REQUIRED_STR) {
      if (typeof o[f] !== 'string' || !(o[f] as string).trim()) {
        errors.push({ index: i, field: f, code: 'bad_string', message: `"${f}" must be a non-empty string.` });
      }
    }
    for (const f of REQUIRED_NUM) {
      if (typeof o[f] !== 'number' || !Number.isFinite(o[f])) {
        errors.push({ index: i, field: f, code: 'bad_number', message: `"${f}" must be a finite number.` });
      }
    }
    if (typeof o.start === 'number' && typeof o.end === 'number' && (o.end as number) <= (o.start as number)) {
      errors.push({ index: i, field: 'end', code: 'range', message: '"end" must be greater than "start".' });
    }
    if (o.note !== undefined && typeof o.note !== 'string') {
      errors.push({ index: i, field: 'note', code: 'bad_string', message: '"note" must be a string if present.' });
    }
    if (typeof o.id === 'string' && o.id.trim()) {
      if (seen.has(o.id)) {
        errors.push({ index: i, field: 'id', code: 'dup_id', message: `Duplicate id "${o.id}".` });
      }
      seen.add(o.id);
    }

    if (errors.length === before) clips.push(o as unknown as Clip);
  });

  return { ok: errors.length === 0, clips, errors };
}
