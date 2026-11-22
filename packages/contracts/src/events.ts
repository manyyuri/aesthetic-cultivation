/**
 * SSE 事件协议（手写，与后端 ac_api/obs/trace.py + orchestrator/core.py 同构）。
 * 改动时两边一起改：make check 会跑契约漂移检查（OpenAPI 部分）。
 */

export type Domain = 'art' | 'music' | 'ballet';

export type StepId =
  | 'candidates'
  | 'retrieve'
  | 'pick'
  | 'anchor'
  | 'write'
  | 'review'
  | 'assemble'
  | 'answer'
  | 'hitl';

export type EvidenceStatus = 'found' | 'weak' | 'insufficient';

export interface RetrievedChunkDto {
  citation_id: string;
  chunk_id: string;
  content: string;
  context_prefix?: string | null;
  source: string;
  locator: { doc_title: string; page?: number | null; anchor?: string | null; url?: string | null };
  doc_id: string;
  domain: string;
  metadata: Record<string, unknown>;
  scores: Record<string, number>;
  source_priority: string;
}

export interface ReviewIssueDto {
  gate: 'evidence' | 'anchor' | 'tone' | 'novelty';
  problem: string;
  fix_hint: string;
}

interface Base {
  seq: number;
  ts?: string;
  run_id?: string;
}

export type RunEvent =
  | (Base & { type: 'run.started'; run_id: string; kind: 'issue_build' | 'ask'; subject_id: string })
  | (Base & { type: 'step.started'; step: StepId; label: string })
  | (Base & {
      type: 'step.finished';
      step: StepId;
      ok: boolean;
      latency_ms: number;
      summary: string;
      payload?: Record<string, unknown> | null;
    })
  | (Base & {
      type: 'retrieval.result';
      attempt: number;
      req: { domain: string; query: string; top_k: number };
      res: {
        evidence_status: EvidenceStatus;
        chunks: RetrievedChunkDto[];
        missing_hint?: string | null;
        suggested_queries?: string[];
        latency_ms: number;
      };
    })
  | (Base & { type: 'candidate.picked'; ord: number; item_id: string; domain: Domain; rank_score: number })
  | (Base & {
      type: 'candidate.rejected';
      item_id: string;
      reason: string;
    })
  | (Base & { type: 'llm.delta'; step: StepId; text: string })
  | (Base & { type: 'review.verdict'; verdict: string; issues: ReviewIssueDto[]; loop: number })
  | (Base & { type: 'claim.checked'; sentence: string; citations: string[]; verdict: 'ok' | 'unsupported' | 'miscitation' })
  | (Base & { type: 'run.finished'; status: 'ready' | 'partial' | 'answered' | 'refused' | 'failed'; issue_id?: string; answer_md?: string })
  | (Base & { type: 'run.error'; code: string; message: string; retryable: boolean });
