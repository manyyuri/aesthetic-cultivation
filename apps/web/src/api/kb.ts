export interface SourceInfo {
  name: string;
  domain: string;
  license: string;
  homepage: string;
  kind: string;
  doc_count: number;
}

export interface KbDoc {
  doc_id: string;
  title: string;
  source_priority: string;
  chunk_count: number;
  ingested_at: string | null;
  source: string;
  license: string | null;
  retrieved_at: string | null;
  source_url: string | null;
}

export interface FetchReport {
  source: string;
  domain: string;
  candidates: number;
  written: number;
  skipped: number;
  dry_run: boolean;
  refused: { external_id: string; reason: string }[];
  missing_meta: Record<string, number>;
}

export interface JobRecord {
  id: string;
  kind: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  report: unknown;
  error: string | null;
}

const KEY = (import.meta.env.VITE_API_KEY as string | undefined) ?? 'dev-local-key';

export async function listSources(): Promise<SourceInfo[]> {
  const res = await fetch('/api/sources');
  return (await res.json()) as SourceInfo[];
}

export async function listDocs(domain: string): Promise<{ domain: string; index_version: string | null; docs: KbDoc[] }> {
  const res = await fetch(`/api/kb/docs?domain=${encodeURIComponent(domain)}`);
  return (await res.json()) as { domain: string; index_version: string | null; docs: KbDoc[] };
}

export async function startFetch(body: {
  source: string;
  limit: number;
  query?: string;
  dry_run: boolean;
}): Promise<{ job_id: string }> {
  const res = await fetch('/api/kb/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': KEY },
    body: JSON.stringify(body),
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload?.error?.message ?? '抓取启动失败');
  return payload as { job_id: string };
}

export async function getJob(jobId: string): Promise<JobRecord> {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) throw new Error('没有这个 job');
  return (await res.json()) as JobRecord;
}
