import { useEffect, useReducer, useRef, useState } from 'react';
import { eventsUrl, fetchRunSnapshot } from '../api/client';
import { initProgress, progressReducer } from '../lib/progressReducer';
import type { JobSnapshot } from '../types';

export type ConnState = 'idle' | 'connecting' | 'open' | 'polling' | 'closed';

const SSE_OPEN_TIMEOUT = 8000;
const MAX_SSE_RETRIES = 3;
const POLL_INTERVAL = 2000;

/** Live per-clip progress for a run: hydrate snapshot, stream SSE, fall back to polling. */
export function useJobProgress(runId: string | null) {
  const [state, dispatch] = useReducer(progressReducer, undefined, initProgress);
  const [conn, setConn] = useState<ConnState>('idle');
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);
  const retries = useRef(0);

  useEffect(() => {
    if (!runId) return;
    dispatch({ type: 'reset' });
    let dead = false;
    const isTerminal = (s: string) => s === 'done' || s === 'error';

    const applySnapshot = (jobs: JobSnapshot[]) =>
      jobs.forEach((j) => dispatch({ type: 'event', event: j }));

    const startPoll = () => {
      setConn('polling');
      const tick = async () => {
        try {
          const snap = await fetchRunSnapshot(runId);
          applySnapshot(snap.jobs);
          if (snap.jobs.length && snap.jobs.every((j) => isTerminal(j.status))) {
            setConn('closed');
            return;
          }
        } catch {
          /* keep polling */
        }
        if (!dead) pollRef.current = window.setTimeout(tick, POLL_INTERVAL);
      };
      tick();
    };

    const fallback = () => {
      esRef.current?.close();
      if (!dead) startPoll();
    };

    const openSse = () => {
      setConn('connecting');
      const src = new EventSource(eventsUrl(runId));
      esRef.current = src;
      const openTimer = window.setTimeout(() => {
        if (src.readyState !== EventSource.OPEN) {
          src.close();
          fallback();
        }
      }, SSE_OPEN_TIMEOUT);

      const onMsg = (ev: MessageEvent) => {
        try {
          dispatch({ type: 'event', event: JSON.parse(ev.data) as JobSnapshot });
        } catch {
          /* ignore malformed */
        }
      };

      src.onopen = () => {
        retries.current = 0;
        clearTimeout(openTimer);
        setConn('open');
      };
      src.addEventListener('progress', onMsg);
      src.addEventListener('end', () => {
        src.close();
        setConn('closed');
      });
      src.onerror = () => {
        if (src.readyState === EventSource.CLOSED) {
          if (++retries.current >= MAX_SSE_RETRIES) {
            src.close();
            fallback();
          }
        }
      };
    };

    // Hydrate from snapshot, then open the stream.
    fetchRunSnapshot(runId)
      .then((s) => {
        if (!dead) applySnapshot(s.jobs);
      })
      .catch(() => {});
    openSse();

    return () => {
      dead = true;
      esRef.current?.close();
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [runId]);

  const allDone =
    state.order.length > 0 &&
    state.order.every((id) => {
      const c = state.byClip.get(id)!;
      return c.status === 'done' || c.status === 'error';
    });

  return { clips: state.byClip, order: state.order, conn, allDone };
}
