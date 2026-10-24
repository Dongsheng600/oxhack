'use client';
import { useEffect, useLayoutEffect, useRef } from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Footer, Heading, Pill, Panel } from '@/components/ui';
import { DiffPreview } from './diff-preview';
import { useRefinement } from './use-refinement';
import './refine.css';
export function Refine() {
  const state = useRefinement(),
    editor = useRef<HTMLTextAreaElement>(null),
    overlay = useRef<HTMLDivElement>(null),
    pendingFocus = useRef<boolean | null>(null),
    { snapshot, result, selected } = state;
  const diff = selected && result?.type === 'multiple_choice';
  const suffix = result?.type === 'autocomplete' ? result.text : '';
  const focus = (atEnd = false) => {
    pendingFocus.current = atEnd;
  };
  useLayoutEffect(() => {
    if (pendingFocus.current === null || !editor.current) return;
    const element = editor.current,
      atEnd = pendingFocus.current;
    pendingFocus.current = null;
    element.focus();
    element.setSelectionRange(
      atEnd ? element.value.length : snapshot.start,
      atEnd ? element.value.length : snapshot.end,
    );
  });
  useLayoutEffect(() => {
    const element = editor.current;
    if (element) {
      element.style.height = 'auto';
      element.style.height = `${Math.max(element.scrollHeight, overlay.current?.scrollHeight || 0, 160)}px`;
    }
  }, [snapshot.prompt, suffix, diff]);
  useEffect(() => {
    if (!diff && editor.current && document.activeElement === editor.current)
      editor.current.setSelectionRange(snapshot.start, snapshot.end);
  }, [snapshot, diff]);
  const accept = () => {
    state.accept(selected || undefined);
    focus(true);
  };
  const dismiss = () => {
    state.dismiss();
    focus();
  };
  const keyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing || state.composing.current) return;
    if (event.key === 'Tab' && result?.type === 'autocomplete') {
      event.preventDefault();
      accept();
    }
    if (event.key === 'Escape' && (result || state.loading)) {
      event.preventDefault();
      event.stopPropagation();
      dismiss();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
      event.preventDefault();
      if (event.shiftKey) state.redo();
      else state.undo();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
      event.preventDefault();
      state.redo();
    }
  };
  return (
    <div
      className="refine-page"
      onKeyDown={(event) => {
        if (
          event.key === 'Escape' &&
          !event.nativeEvent.isComposing &&
          !state.composing.current &&
          (result || state.loading)
        ) {
          event.preventDefault();
          dismiss();
        }
      }}
    >
      <Heading action={<Pill green>Draft</Pill>}>Refine your prompt</Heading>
      {state.notice && (
        <div className="accepted-banner" role="status">
          {state.notice}
          {state.notice === 'Changes applied' && (
            <Button
              onClick={() => {
                state.undo();
                focus();
              }}
            >
              Undo
            </Button>
          )}
        </div>
      )}
      <div className="refine-grid">
        <div>
          <Panel
            title={diff ? 'Review changes' : 'Your prompt'}
            meta={
              <span className="count">
                {diff
                  ? `${selected.edits.length} edits`
                  : `REV ${String(snapshot.revision).padStart(2, '0')}`}
              </span>
            }
            className="draft-card"
          >
            {diff ? (
              <DiffPreview
                prompt={snapshot.prompt}
                revision={snapshot.revision}
                edits={selected.edits}
              />
            ) : (
              <div className="editor-region">
                <div className="editor-stack">
                  <label className="sr-only" htmlFor="draft">
                    Draft prompt
                  </label>
                  <div aria-hidden="true" className="ghost-overlay" ref={overlay}>
                    <span className="typed">{snapshot.prompt}</span>
                    {suffix && <span className="ghost">{suffix}</span>}
                  </div>
                  <textarea
                    id="draft"
                    ref={editor}
                    className="draft-input"
                    placeholder="What would you like Codex to do?"
                    spellCheck={false}
                    value={snapshot.prompt}
                    onChange={(event) =>
                      state.change(
                        event.target.value,
                        event.target.selectionStart,
                        event.target.selectionEnd,
                      )
                    }
                    onSelect={(event) => {
                      const target = event.currentTarget;
                      state.moveCursor(target.selectionStart, target.selectionEnd);
                    }}
                    onKeyDown={keyDown}
                    onCompositionStart={state.beginComposition}
                    onCompositionEnd={state.endComposition}
                  />
                </div>
              </div>
            )}
            <div className="draft-foot">
              <span>{diff ? 'Not applied' : `${snapshot.prompt.length} characters`}</span>
              {diff ? <span>1 option selected</span> : <span>Plain text</span>}
            </div>
          </Panel>
          {!diff && (
            <div className="prompt-actions">
              <span>Draft only</span>
              <Button
                primary
                disabled={!snapshot.prompt}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(snapshot.prompt);
                    toast.success('Prompt copied');
                  } catch {
                    toast.error('Copy failed. Select the prompt and copy it manually.');
                  }
                }}
              >
                Copy prompt
              </Button>
            </div>
          )}
        </div>
        <aside>
          <section className="suggestion" aria-live="polite" aria-busy={state.loading}>
            <div className="suggestion-top">
              <span className="eyebrow">
                {result?.type === 'autocomplete'
                  ? 'Autocomplete'
                  : result?.type === 'multiple_choice'
                    ? 'Clarify'
                    : 'Enhancement'}
              </span>
              <Pill error={!!state.error} green={!!result}>
                {state.loading
                  ? 'Working'
                  : state.error
                    ? 'Unavailable'
                    : result?.type === 'none'
                      ? 'Up to date'
                      : result?.type === 'multiple_choice'
                        ? '1 question'
                        : result
                          ? 'Suggestion'
                          : snapshot.prompt
                            ? 'Ready'
                            : 'Idle'}
              </Pill>
            </div>
            {state.loading ? (
              <>
                <div className="loading-bar" />
                <h2>Checking your prompt</h2>
                <Button onClick={dismiss}>Cancel</Button>
              </>
            ) : state.error ? (
              <>
                <div className="error-box" role="alert">
                  <h2>Enhancement failed</h2>
                  <p>{state.error}</p>
                </div>
                <div className="actions">
                  <Button onClick={dismiss}>Continue writing</Button>
                  <Button primary onClick={() => void state.enhance()}>
                    Retry
                  </Button>
                </div>
              </>
            ) : result?.type === 'autocomplete' ? (
              <>
                <h2>Complete your prompt.</h2>
                <p className="snippet">{result.text}</p>
                <div className="actions">
                  <Button onClick={dismiss}>Dismiss</Button>
                  <Button primary onClick={accept}>
                    Accept <kbd>Tab</kbd>
                  </Button>
                </div>
              </>
            ) : result?.type === 'multiple_choice' ? (
              <>
                <h2>{result.question}</h2>
                <fieldset className="choice-group">
                  <legend className="sr-only">{result.question}</legend>
                  {result.options.map((option) => (
                    <label
                      key={option.id}
                      className={`choice ${option.id === selected?.id ? 'selected' : ''}`}
                    >
                      <input
                        type="radio"
                        name="enhancement-option"
                        checked={option.id === selected?.id}
                        onChange={() => state.setSelected(option)}
                      />
                      {option.label}
                    </label>
                  ))}
                </fieldset>
                {selected ? (
                  <div className="actions">
                    <Button
                      onClick={() => {
                        state.setSelected(null);
                        focus();
                      }}
                    >
                      Back
                    </Button>
                    <Button primary onClick={accept}>
                      Confirm changes
                    </Button>
                  </div>
                ) : (
                  <Button className="decline" onClick={dismiss}>
                    Decline all
                  </Button>
                )}
              </>
            ) : (
              <>
                <h2>
                  {result?.type === 'none'
                    ? 'No suggestion'
                    : snapshot.prompt
                      ? 'Ready to check'
                      : 'No draft yet'}
                </h2>
                {!snapshot.prompt && (
                  <p className="status-message muted">Enter a prompt to request suggestions.</p>
                )}
                <Button
                  primary
                  disabled={!snapshot.prompt.trim() || !state.ready}
                  onClick={() => void state.enhance()}
                >
                  Enhance
                </Button>
              </>
            )}
            {snapshot.prompt && (
              <div className="suggestion-meta">
                <span>REV {String(snapshot.revision).padStart(2, '0')}</span>
                <span>{result && result.type !== 'none' ? 'Not applied' : ''}</span>
              </div>
            )}
          </section>
          {state.sources.length > 0 && (
            <div className="sources">
              <div className="eyebrow">Referenced knowledge · {state.sources.length}</div>
              {state.sources.map((source) => (
                <Link
                  key={source.id}
                  href={`/knowledge/${encodeURIComponent(source.id)}`}
                  className="source-item"
                >
                  <span className="file-kind">{source.kind.toUpperCase()}</span>
                  <span>{source.title}</span>
                  <ArrowUpRight className="icon" />
                </Link>
              ))}
            </div>
          )}
        </aside>
      </div>
      <Footer
        left={state.requestId ? `REQUEST ${state.requestId}` : 'No request yet'}
        right={state.loading ? 'Checking…' : undefined}
      />
    </div>
  );
}
