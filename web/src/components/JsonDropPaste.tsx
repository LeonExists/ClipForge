import { useCallback, useRef, useState } from 'react';
import { parseClipsJson } from '../lib/validateClips';
import type { Clip } from '../types';
import styles from './JsonDropPaste.module.css';

interface Props {
  onClips: (clips: Clip[]) => void;
  disabled?: boolean;
}

export function JsonDropPaste({ onClips, disabled }: Props) {
  const [text, setText] = useState('');
  const [errors, setErrors] = useState<string[]>([]);
  const [count, setCount] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const timer = useRef<number | null>(null);

  const parse = useCallback(
    (value: string) => {
      const res = parseClipsJson(value);
      if (!value.trim()) {
        setErrors([]);
        setCount(null);
        onClips([]);
        return;
      }
      if (res.ok) {
        setErrors([]);
        setCount(res.clips.length);
        onClips(res.clips);
      } else {
        setErrors(res.errors.map((e) => e.message));
        setCount(null);
        onClips([]);
      }
    },
    [onClips]
  );

  const onChange = (value: string) => {
    setText(value);
    if (timer.current) clearTimeout(timer.current);
    timer.current = window.setTimeout(() => parse(value), 200);
  };

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) {
      const content = await file.text();
      setText(content);
      parse(content);
    }
  };

  return (
    <div className={styles.wrap}>
      <label className={styles.label}>Clip definitions (JSON)</label>
      <div
        className={`${styles.drop} ${dragging ? styles.dragging : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <textarea
          className={styles.textarea}
          placeholder='Paste the exported JSON array here, or drop a .json file…'
          value={text}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
        />
      </div>
      {count !== null && (
        <div className={styles.ok}>✓ {count} clip{count === 1 ? '' : 's'} parsed</div>
      )}
      {errors.length > 0 && (
        <ul className={styles.errors}>
          {errors.slice(0, 8).map((e, i) => (
            <li key={i}>{e}</li>
          ))}
          {errors.length > 8 && <li>…and {errors.length - 8} more</li>}
        </ul>
      )}
    </div>
  );
}
