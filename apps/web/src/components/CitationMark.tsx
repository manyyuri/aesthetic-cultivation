import { Fragment, type ReactNode } from 'react';
import { splitCitations } from '../lib/citations';

export function CitationMark({ mark, onClick }: { mark: string; onClick: () => void }) {
  return (
    <button type="button" className="cite" onClick={onClick} title="查看出处">
      {mark}
    </button>
  );
}

/** 把正文里的 [S1] 渲染成可点的展签编号，而不是蓝色角标 */
export function renderWithCitations(text: string, onCite: (id: string) => void): ReactNode[] {
  return splitCitations(text).map((part, index) =>
    part.kind === 'cite' ? (
      <button key={`c${index}`} type="button" className="cite inline" onClick={() => onCite(part.id)}>
        {part.id}
      </button>
    ) : (
      <Fragment key={`t${index}`}>{part.value}</Fragment>
    ),
  );
}
