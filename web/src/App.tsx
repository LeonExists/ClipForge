import { useEffect, useState } from 'react';
import './styles/global.css';
import styles from './App.module.css';
import { JsonDropPaste } from './components/JsonDropPaste';
import { ClipList } from './components/ClipList';
import { ConfigPanel } from './components/ConfigPanel';
import { RunButton } from './components/RunButton';
import { ProgressCard } from './components/ProgressCard';
import { useJobProgress } from './hooks/useJobProgress';
import { fetchHealth, fetchPresets, submitRun, zipUrl } from './api/client';
import { DEFAULT_CONFIG, type Clip, type JobConfig, type Preset } from './types';

export default function App() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [config, setConfig] = useState<JobConfig>(DEFAULT_CONFIG);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [health, setHealth] = useState<Record<string, boolean> | null>(null);

  const { clips: progress, order, conn, allDone } = useJobProgress(runId);

  useEffect(() => {
    fetchPresets().then(setPresets).catch(() => {});
    fetchHealth().then(setHealth).catch(() => {});
  }, []);

  const toolMissing = health && !health.ok;

  const run = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await submitRun(clips, config);
      setRunId(res.runId);
    } catch (e) {
      setSubmitError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setRunId(null);
    setSubmitError(null);
  };

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.logo}>◆</span>
          <h1>ClipForge</h1>
          <span className={styles.tagline}>YouTube clips → captioned vertical shorts</span>
        </div>
        {runId && (
          <button className="btn" onClick={reset}>
            New batch
          </button>
        )}
      </header>

      {toolMissing && (
        <div className={styles.banner}>
          Missing tools:{' '}
          {Object.entries(health!)
            .filter(([k, v]) => k !== 'ok' && !v)
            .map(([k]) => k)
            .join(', ')}
          . Install ffmpeg + yt-dlp and reload.
        </div>
      )}

      <main className={styles.main}>
        <section className={styles.left}>
          <JsonDropPaste onClips={setClips} disabled={!!runId} />
          {clips.length > 0 && (
            <>
              <ConfigPanel config={config} presets={presets} onChange={setConfig} disabled={!!runId} />
              {!runId && (
                <>
                  <RunButton
                    disabled={clips.length === 0 || submitting}
                    submitting={submitting}
                    count={clips.length}
                    onRun={run}
                  />
                  {submitError && <div className={styles.error}>{submitError}</div>}
                </>
              )}
            </>
          )}
        </section>

        <section className={styles.right}>
          {clips.length > 0 && !runId && <ClipList clips={clips} />}
          {runId && (
            <div className={styles.results}>
              <div className={styles.resultsHead}>
                <h2>Progress</h2>
                <span className={styles.conn} data-conn={conn}>
                  {conn}
                </span>
                {allDone && (
                  <a className="btn btn-primary" href={zipUrl(runId)}>
                    Download all (ZIP)
                  </a>
                )}
              </div>
              {order.map((id) => (
                <ProgressCard key={id} runId={runId} progress={progress.get(id)!} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
