import { Fragment, type ReactNode } from 'react';

const CITE = /\[(S\d+)\]/g;

export function CitationMark({ mark, onClick }: { mark: string; onClick: () => void }) {
  return (
    <button type="button" className="cite" onClick={onClick} title="查看出处">
      {mark}
    </button>
  );
}

/** 把正文里的 [S1] 渲染成可点的展签编号，而不是蓝色角标 */
export function renderWithCitations(text: string, onCite: (id: string) => void): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  CITE.lastIndex = 0;
  while ((match = CITE.exec(text)) !== null) {
    if (match.index > last) nodes.push(<Fragment key={`t${last}`}>{text.slice(last, match.index)}</Fragment>);
    const id = match[1];
    nodes.push(
      <button key={`c${match.index}`} type="button" className="cite inline" onClick={() => onCite(id)}>
        {id}
      </button>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(<Fragment key={`t${last}`}>{text.slice(last)}</Fragment>);
  return nodes;
}
