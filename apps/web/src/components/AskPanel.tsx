import { useCallback, useEffect, useRef, useState } from 'react';
import type { RunEvent, RetrievedChunkDto } from '@ac/contracts/events';
import type { Item } from '../api/client';
import { renderWithCitations } from './CitationMark';

type Phase = 'idle' | 'running' | 'answered' | 'refused' | 'failed';

interface AskState {
  phase: Phase;
  runId: string | null;
  answer: string;
  chunks: RetrievedChunkDto[];
  checks: { sentence: string; ok: boolean }[];
  error: string | null;
  missingHint: string | null;
}

const INITIAL: AskState = {
  phase: 'idle',
  runId: null,
  answer: '',
  chunks: [],
  checks: [],
  error: null,
  missingHint: null,
};

const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined) ?? 'dev-local-key';

export function AskPanel({ item, compact = false }: { item: Item; compact?: boolean }) {
  const [question, setQuestion] = useState('');
  const [state, setState] = useState<AskState>(INITIAL);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => () => esRef.current?.close(), []);

  const ask = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q) return;
      esRef.current?.close();
      setState({ ...INITIAL, phase: 'running' });
      try {
        const res = await fetch(`/api/items/${item.id}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
          body: JSON.stringify({ question: q }),
        });
        const body = await res.json();
        if (!res.ok) {
          setState((s) => ({ ...s, phase: 'failed', error: body?.error?.message ?? '请求失败' }));
          return;
        }
        const runId: string = body.run_id;
        setState((s) => ({ ...s, runId }));
        const es = new EventSource(`/api/runs/${runId}/stream`);
        esRef.current = es;

        const handle = (evt: MessageEvent) => {
          const event = JSON.parse(evt.data) as RunEvent;
          if (event.type === 'llm.delta') {
            setState((s) => ({ ...s, answer: s.answer + event.text }));
          } else if (event.type === 'retrieval.result') {
            setState((s) => ({
              ...s,
              chunks: event.res.chunks,
              missingHint: event.res.missing_hint ?? null,
            }));
          } else if (event.type === 'claim.checked') {
            setState((s) => ({
              ...s,
              checks: [...s.checks, { sentence: event.sentence, ok: event.verdict === 'ok' }],
            }));
          } else if (event.type === 'run.finished') {
            setState((s) => ({
              ...s,
              phase: event.status === 'refused' ? 'refused' : 'answered',
              answer: event.answer_md ?? s.answer,
            }));
            es.close();
          } else if (event.type === 'run.error') {
            setState((s) => ({ ...s, phase: 'failed', error: event.message }));
            es.close();
          }
        };

        for (const type of [
          'run.started',
          'step.finished',
          'retrieval.result',
          'llm.delta',
          'claim.checked',
          'review.verdict',
          'run.finished',
          'run.error',
        ]) {
          es.addEventListener(type, handle as EventListener);
        }
        es.onerror = () => {
          setState((s) => (s.phase === 'running' ? { ...s, phase: 'failed', error: '连接中断' } : s));
          es.close();
        };
      } catch (err) {
        setState((s) => ({ ...s, phase: 'failed', error: String(err) }));
      }
    },
    [item.id],
  );

  return (
    <section className={`ask ${compact ? 'compact' : ''}`}>
      <form
        className="ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
      >
        <label className="t-archive ask-label" htmlFor={`ask-${item.id}`}>
          问一句
        </label>
        <input
          id={`ask-${item.id}`}
          className="ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`关于${item.title_zh}，你想再确认什么？`}
        />
        <button className="ghost" type="submit" disabled={state.phase === 'running'}>
          {state.phase === 'running' ? '在查' : '问'}
        </button>
      </form>

      {state.phase === 'failed' ? <p className="ask-error">没查成：{state.error}</p> : null}

      {state.phase === 'refused' || (state.phase === 'answered' && state.answer.startsWith('资料里没有')) ? (
        <div className="ask-refusal">
          <p className="t-archive">资料不足</p>
          <p>{state.answer || '知识库里没有能支撑这个问题的原文。'}</p>
          {state.missingHint ? <p className="t-archive muted">{state.missingHint}</p> : null}
        </div>
      ) : null}

      {state.answer && !state.answer.startsWith('资料里没有') ? (
        <div className="ask-answer">
          {renderWithCitations(state.answer, (id) => {
            const chunk = state.chunks.find((c) => c.citation_id === id);
            if (!chunk) return;
            setState((s) => ({ ...s, missingHint: chunk.source }));
          })}
        </div>
      ) : null}

      {state.chunks.length ? (
        <ul className="ask-evidence">
          {state.chunks.map((chunk) => (
            <li key={chunk.chunk_id}>
              <span className="t-archive">{chunk.citation_id}</span>
              <span>{chunk.source}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {state.checks.some((c) => !c.ok) ? (
        <p className="ask-error">有句子的引用没对上原文，已标出来：{state.checks.filter((c) => !c.ok).length} 句。</p>
      ) : null}
    </section>
  );
}
