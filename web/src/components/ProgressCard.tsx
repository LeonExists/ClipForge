import { useState } from 'react';
import { outputUrl } from '../api/client';
import { stageState, type ClipProgress } from '../lib/progressReducer';
import { STAGES, type Stage } from '../types';
import styles from './ProgressCard.module.css';

const STAGE_LABELS: Record<Stage, string> = {
  download: 'Download',
  transcribe: 'Transcribe',
  caption: 'Caption',
  render: 'Render',
  done: 'Done',
};

export function ProgressCard({ runId, progress }: { runId: string; progress: ClipProgress }) {
  const [showPreview, setShowPreview] = useState(false);
  const p = progress;
  const done = p.status === 'done';
  const errored = p.status === 'error';

  return (
    <div className={`${styles.card} ${errored ? styles.errored : ''}`}>
      <div className={styles.top}>
        <span className={styles.title}>{p.title ?? p.clipId}</span>
        <span className={styles.pct}>{errored ? 'error' : `${Math.round(p.pct)}%`}</span>
      </div>

      <div className={styles.stepper}>
        {STAGES.map((s) => {
          const st = stageState(p, s);
          return (
            <div key={s} className={styles.step} data-state={st}>
              <span className={styles.dot} />
              <span className={styles.stepLabel}>{STAGE_LABELS[s]}</span>
            </div>
          );
        })}
      </div>

      {!done && !errored && (
        <div className={styles.bar}>
          <div className={styles.fill} style={{ width: `${p.pct}%` }} />
        </div>
      )}

      {p.message && !errored && <div className={styles.msg}>{p.message}</div>}
      {errored && <div className={styles.err}>{p.error ?? p.message}</div>}

      {done && (
        <div className={styles.actions}>
          <button className="btn" onClick={() => setShowPreview((v) => !v)}>
            {showPreview ? 'Hide preview' : 'Preview'}
          </button>
          <a className="btn btn-primary" href={outputUrl(runId, p.clipId, p.ts)} download>
            Download
          </a>
        </div>
      )}

      {done && showPreview && (
        <div className={styles.preview}>
          <video controls src={outputUrl(runId, p.clipId, p.ts)} />
        </div>
      )}
    </div>
  );
}
