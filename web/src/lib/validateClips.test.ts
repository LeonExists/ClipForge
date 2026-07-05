import { describe, expect, it } from 'vitest';
import { parseClipsJson, validateClips } from './validateClips';

const VALID = {
  createdAt: '2026-07-03T14:48:23.279Z',
  end: 36.33,
  id: 'abc-1',
  note: '',
  start: 21.61,
  title: "Stable Ronaldo's Funniest Moments!",
  url: 'https://www.youtube.com/watch?v=Q260EqSF5aA',
  videoId: 'Q260EqSF5aA',
};

describe('validateClips', () => {
  it('accepts a valid array', () => {
    const r = validateClips([VALID]);
    expect(r.ok).toBe(true);
    expect(r.clips).toHaveLength(1);
  });

  it('rejects a non-array root', () => {
    const r = validateClips({});
    expect(r.ok).toBe(false);
    expect(r.errors[0].code).toBe('not_array');
  });

  it('rejects a non-object item', () => {
    const r = validateClips(['nope']);
    expect(r.ok).toBe(false);
    expect(r.errors[0].code).toBe('not_object');
  });

  it('flags missing required strings', () => {
    const { url, ...rest } = VALID;
    const r = validateClips([rest]);
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.field === 'url')).toBe(true);
  });

  it('flags non-finite numbers', () => {
    const r = validateClips([{ ...VALID, start: 'x' }]);
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.field === 'start')).toBe(true);
  });

  it('flags end <= start', () => {
    const r = validateClips([{ ...VALID, start: 40, end: 36 }]);
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.code === 'range')).toBe(true);
  });

  it('flags duplicate ids', () => {
    const r = validateClips([VALID, { ...VALID }]);
    expect(r.ok).toBe(false);
    expect(r.errors.some((e) => e.code === 'dup_id')).toBe(true);
  });

  it('flags non-string note', () => {
    const r = validateClips([{ ...VALID, note: 5 }]);
    expect(r.ok).toBe(false);
  });

  it('tolerates extra keys', () => {
    const r = validateClips([{ ...VALID, extra: 1 }]);
    expect(r.ok).toBe(true);
  });

  it('carries index + field on errors', () => {
    const r = validateClips([VALID, { ...VALID, id: 'x', title: '' }]);
    const e = r.errors.find((x) => x.field === 'title');
    expect(e?.index).toBe(1);
  });
});

describe('parseClipsJson', () => {
  it('reports malformed JSON without throwing', () => {
    const r = parseClipsJson('{not json');
    expect(r.ok).toBe(false);
    expect(r.errors[0].code).toBe('invalid_json');
  });

  it('parses valid JSON text', () => {
    const r = parseClipsJson(JSON.stringify([VALID]));
    expect(r.ok).toBe(true);
  });
});
