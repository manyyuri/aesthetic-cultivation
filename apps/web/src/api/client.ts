import createClient from 'openapi-fetch';
import type { paths } from '@ac/contracts';

const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined) ?? 'dev-local-key';

export const api = createClient<paths>({
  baseUrl: '',
  headers: { 'X-API-Key': API_KEY },
});

export type Issue = {
  id: string;
  kind: 'daily' | 'weekly';
  issue_no: number;
  publish_date: string;
  title: string;
  subtitle: string;
  minutes: number;
  status: 'draft' | 'ready' | 'delivered' | 'partial';
  generated_at?: string | null;
  delivered_at?: string | null;
  items: Item[];
};

export type Item = {
  id: string;
  issue_id: string;
  ord: number;
  domain: 'art' | 'music' | 'ballet' | string;
  title_zh: string;
  title_orig?: string | null;
  meta_lines: { k: string; v: string }[];
  hook: string;
  anchor: { kind: 'look' | 'listen' | 'watch'; label: string; spec: Record<string, unknown> };
  evidence: {
    mark: string;
    chunk_id: string;
    doc_id: string;
    source: string;
    excerpt: string;
    scores: Record<string, number>;
  }[];
  image_url?: string | null;
  done_at?: string | null;
  rank_score: number;
};

export const DOMAIN_LABEL: Record<string, string> = {
  art: '美术馆',
  music: '音乐会',
  ballet: '芭蕾',
};

export const ROMAN = ['', 'Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ'];

/** 远程图走本地代理：热链会 403，且展签不能因为图挂了就空一块 */
export function mediaUrl(raw?: string | null): string | null {
  if (!raw) return null;
  return `/api/media?src=${encodeURIComponent(raw)}`;
}

/** 缺素材时说的话按领域走：美术馆说图版，音乐会说录音，芭蕾说剧照 */
export const MEDIA_MISSING: Record<string, string> = {
  art: '图版待补',
  music: '录音待补',
  ballet: '剧照待补',
};
