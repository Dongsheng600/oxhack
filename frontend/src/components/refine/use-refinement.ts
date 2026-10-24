'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, post, uid, errorMessage } from '@/lib/api';
import { applyEdits, parseEnhancement } from '@/lib/edits';
import type { EnhanceRequest, EnhanceResponse, Option, Source } from '@/lib/types';

type Snapshot = {
  prompt: string;
  revision: number;
  start: number;
  end: number;
  generation: number;
};
type Result = { response: EnhanceResponse; snapshot: Snapshot };
export function useRefinement() {
  const [snapshot, setSnapshot] = useState<Snapshot>({
    prompt: '',
    revision: 0,
    start: 0,
    end: 0,
    generation: 0,
  });
  const current = useRef(snapshot),
    sequence = useRef(0),
    controller = useRef<AbortController | null>(null);
  const [isComposing, setIsComposing] = useState(false);
  const [ready, setReady] = useState(false),
    [loading, setLoading] = useState(false),
    [result, setResult] = useState<Result | null>(null),
    [error, setError] = useState<string | null>(null),
    [sources, setSources] = useState<Source[]>([]),
    [selected, setSelected] = useState<Option | null>(null),
    [notice, setNotice] = useState(''),
    [requestId, setRequestId] = useState<string | null>(null);
  const resultRef = useRef<Result | null>(null),
    history = useRef<string[]>([]),
    future = useRef<string[]>([]),
    composing = useRef(false),
    active = useRef(true);
  const outcome = useCallback((id: string, event_type: string) => {
    void post('/outcomes', { event_id: uid(), request_id: id, event_type }).catch(() => {
      /* Operational outcomes never change draft state. */
    });
  }, []);
  const clear = useCallback(
    (event: 'stale' | 'declined' | null = 'stale') => {
      sequence.current++;
      controller.current?.abort();
      controller.current = null;
      if (resultRef.current && event) outcome(resultRef.current.response.request_id, event);
      resultRef.current = null;
      setResult(null);
      setSelected(null);
      setSources([]);
      setError(null);
      setLoading(false);
    },
    [outcome],
  );
  const change = useCallback(
    (prompt: string, start: number, end = start, record = true) => {
      const previous = current.current;
      if (prompt === previous.prompt && start === previous.start && end === previous.end) return;
      if (prompt !== previous.prompt && record) {
        history.current.push(previous.prompt);
        future.current = [];
      }
      clear();
      if (prompt !== previous.prompt) setNotice('');
      const next = {
        prompt,
        revision: previous.revision + (prompt !== previous.prompt ? 1 : 0),
        start,
        end,
        generation: previous.generation + 1,
      };
      current.current = next;
      setSnapshot(next);
      try {
        localStorage.setItem('prompt-enhance.draft', prompt);
      } catch {
        /* Storage may be disabled. */
      }
    },
    [clear],
  );
  useEffect(() => {
    active.current = true;
    try {
      const prompt = localStorage.getItem('prompt-enhance.draft') || '';
      const next = { prompt, revision: 0, start: prompt.length, end: prompt.length, generation: 0 };
      current.current = next;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Browser storage is intentionally hydrated after server rendering.
      setSnapshot(next);
    } catch {
      /* Start an empty draft. */
    }
    setReady(true);
    return () => {
      active.current = false;
      controller.current?.abort();
    };
  }, []);
  const matches = useCallback((value: Snapshot) => {
    const now = current.current;
    return (
      now.generation === value.generation &&
      now.prompt === value.prompt &&
      now.revision === value.revision &&
      now.start === value.start &&
      now.end === value.end
    );
  }, []);
  const enhance = useCallback(async () => {
    const value = { ...current.current };
    if (!value.prompt.trim() || composing.current || value.start !== value.end) return;
    clear(null);
    setNotice('');
    const seq = sequence.current,
      abort = new AbortController();
    controller.current = abort;
    const request: EnhanceRequest = {
      request_id: uid(),
      prompt: value.prompt,
      prompt_revision: value.revision,
      cursor_position: value.start,
    };
    setRequestId(request.request_id);
    setLoading(true);
    try {
      const raw = await post<unknown>('/enhance', request, abort.signal);
      if (!active.current || seq !== sequence.current || !matches(value)) {
        outcome(request.request_id, 'stale');
        return;
      }
      const response = parseEnhancement(raw, request),
        next = { response, snapshot: value };
      resultRef.current = next;
      setResult(next);
      setLoading(false);
      outcome(request.request_id, 'displayed');
      void api<{ sources: Source[] }>(
        `/enhancements/${encodeURIComponent(request.request_id)}/sources`,
        { signal: abort.signal },
      )
        .then((data) => {
          if (active.current && seq === sequence.current && matches(value))
            setSources(data.sources);
        })
        .catch(() => {});
    } catch (cause) {
      if (!active.current || seq !== sequence.current || !matches(value) || abort.signal.aborted)
        return;
      setError(errorMessage(cause));
      setLoading(false);
      outcome(request.request_id, 'failed');
    }
  }, [clear, matches, outcome]);
  useEffect(() => {
    if (
      !ready ||
      !snapshot.prompt.trim() ||
      isComposing ||
      snapshot.start !== snapshot.end ||
      result ||
      error ||
      notice
    )
      return;
    const timer = setTimeout(() => void enhance(), 700);
    return () => clearTimeout(timer);
  }, [snapshot, ready, isComposing, enhance, result, error, notice]);
  const accept = useCallback(
    (option?: Option) => {
      const eligible = resultRef.current;
      if (!eligible || !matches(eligible.snapshot)) {
        clear();
        return false;
      }
      let next: string;
      try {
        if (option && eligible.response.type === 'multiple_choice') {
          const valid = eligible.response.options.find((item) => item.id === option.id);
          if (!valid) return false;
          next = applyEdits(eligible.snapshot.prompt, valid.edits);
        } else if (eligible.response.type === 'autocomplete')
          next = applyEdits(eligible.snapshot.prompt, [
            {
              start: eligible.response.insert_at,
              end: eligible.response.insert_at,
              text: eligible.response.text,
            },
          ]);
        else return false;
      } catch (cause) {
        setError(errorMessage(cause));
        return false;
      }
      outcome(eligible.response.request_id, 'accepted');
      resultRef.current = null;
      change(next, next.length);
      setNotice('Changes applied');
      return true;
    },
    [matches, clear, change, outcome],
  );
  const dismiss = useCallback(() => {
    clear('declined');
    setNotice('Suggestion dismissed');
  }, [clear]);
  const undo = useCallback(() => {
    const previous = history.current.pop();
    if (previous === undefined) return;
    future.current.push(current.current.prompt);
    change(previous, previous.length, previous.length, false);
    setNotice('Change undone');
  }, [change]);
  const redo = useCallback(() => {
    const next = future.current.pop();
    if (next === undefined) return;
    history.current.push(current.current.prompt);
    change(next, next.length, next.length, false);
    setNotice('Change restored');
  }, [change]);
  const moveCursor = (start: number, end: number) => {
    const prompt = current.current.prompt;
    change(prompt, Math.min(start, prompt.length), Math.min(end, prompt.length));
  };
  const beginComposition = () => {
    composing.current = true;
    setIsComposing(true);
    clear();
  };
  const endComposition = () => {
    composing.current = false;
    setIsComposing(false);
  };
  return {
    moveCursor,
    beginComposition,
    endComposition,
    snapshot,
    ready,
    loading,
    result: result?.response || null,
    error,
    sources,
    selected,
    setSelected,
    notice,
    requestId,
    change,
    enhance,
    accept,
    dismiss,
    undo,
    redo,
    composing,
    clear,
  };
}
