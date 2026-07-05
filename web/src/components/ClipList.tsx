import { clipStats, groupByVideoId } from '../lib/grouping';
import { formatRange } from '../lib/format';
import type { Clip } from '../types';
import styles from './ClipList.module.css';

export function ClipList({ clips }: { clips: Clip[] }) {
  const stats = clipStats(clips);
  const groups = groupByVideoId(clips);

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2>Clips</h2>
        <span className={styles.count}>
          {stats.clipCount} clip{stats.clipCount === 1 ? '' : 's'} · {stats.videoCount} source
          {stats.videoCount === 1 ? '' : 's'}
        </span>
        {stats.hasSharedSources && (
          <span className={styles.badge} title="Shared videoId — downloaded efficiently, not re-fetched">
            shared sources
          </span>
        )}
      </div>

      {groups.map((g) => (
        <div key={g.videoId} className={styles.group}>
          {g.clips.length > 1 && (
            <div className={styles.groupLabel}>
              <span className="mono">{g.videoId}</span> · {g.clips.length} clips
            </div>
          )}
          {g.clips.map((c) => (
            <div key={c.id} className={styles.clip}>
              <div className={styles.title}>{c.title}</div>
              <div className={styles.meta}>
                <span>{formatRange(c.start, c.end)}</span>
                {c.note && <span className={styles.note}>{c.note}</span>}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
