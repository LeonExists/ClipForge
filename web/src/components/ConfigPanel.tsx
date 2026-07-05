import type { JobConfig, Preset, ReframeMode, WhisperModel } from '../types';
import styles from './ConfigPanel.module.css';

interface Props {
  config: JobConfig;
  presets: Preset[];
  onChange: (c: JobConfig) => void;
  disabled?: boolean;
}

const WHISPER_MODELS: WhisperModel[] = [
  'small.en', 'small', 'base.en', 'base', 'tiny.en', 'tiny', 'medium.en', 'medium', 'large-v3',
];

export function ConfigPanel({ config, presets, onChange, disabled }: Props) {
  const set = <K extends keyof JobConfig>(k: K, v: JobConfig[K]) => onChange({ ...config, [k]: v });

  return (
    <div className={styles.panel}>
      <label className={styles.groupLabel}>Settings</label>

      <div className={styles.row}>
        <span className={styles.name}>Reframe</span>
        <div className={styles.seg}>
          {(['crop', 'blur_pad'] as ReframeMode[]).map((m) => (
            <button
              key={m}
              className={config.reframe_mode === m ? styles.segActive : styles.segBtn}
              disabled={disabled}
              onClick={() => set('reframe_mode', m)}
            >
              {m === 'crop' ? 'Crop' : 'Blur pad'}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.row}>
        <span className={styles.name}>Whisper model</span>
        <select
          className={styles.select}
          value={config.whisper_model}
          disabled={disabled}
          onChange={(e) => set('whisper_model', e.target.value as WhisperModel)}
        >
          {WHISPER_MODELS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.row}>
        <span className={styles.name}>Caption preset</span>
        <select
          className={styles.select}
          value={config.caption_preset}
          disabled={disabled}
          onChange={(e) => set('caption_preset', e.target.value)}
        >
          {(presets.length ? presets : [{ id: 'shorts_bold', label: 'Shorts Bold' }]).map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.row}>
        <span className={styles.name}>Precise cuts</span>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={config.precise_cuts}
            disabled={disabled}
            onChange={(e) => set('precise_cuts', e.target.checked)}
          />
          <span className={styles.slider} />
        </label>
      </div>
    </div>
  );
}
