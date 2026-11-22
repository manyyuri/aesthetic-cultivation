/** 把答案里的 [S1] 切成"文字 / 引用"两段，渲染层不关心正则。 */
export type CitationPart = { kind: 'text'; value: string } | { kind: 'cite'; id: string };

const CITE = /\[(S\d+)\]/g;

export function splitCitations(text: string): CitationPart[] {
  const parts: CitationPart[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  CITE.lastIndex = 0;
  while ((match = CITE.exec(text)) !== null) {
    if (match.index > last) parts.push({ kind: 'text', value: text.slice(last, match.index) });
    parts.push({ kind: 'cite', id: match[1] });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ kind: 'text', value: text.slice(last) });
  return parts;
}

/** 取答案里出现过的引用编号（去重、保序） */
export function citedIds(text: string): string[] {
  const seen: string[] = [];
  for (const part of splitCitations(text)) {
    if (part.kind === 'cite' && !seen.includes(part.id)) seen.push(part.id);
  }
  return seen;
}
