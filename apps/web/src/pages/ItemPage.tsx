import { Link, useParams } from 'react-router-dom';
import { useState } from 'react';
import { DOMAIN_LABEL, MEDIA_MISSING, ROMAN, mediaUrl } from '../api/client';
import { useIssue, useItem, useToggleDone } from '../api/hooks';
import { WallLabel } from '../components/WallLabel';
import { AskPanel } from '../components/AskPanel';
import { CitationMark } from '../components/CitationMark';

export function ItemPage() {
  const { itemId } = useParams();
  const { data: item, isLoading } = useItem(itemId);
  const { data: issue } = useIssue(item?.issue_id);
  const toggle = useToggleDone();
  const [active, setActive] = useState<string | null>(null);

  if (isLoading || !item) return <div className="page"><div className="skeleton-body" /></div>;

  return (
    <div className="itempage">
      <p className="crumbs t-archive">
        <Link to={issue ? `/issues/${issue.id}` : '/'}>第 {String(issue?.issue_no ?? 0).padStart(3, '0')} 期</Link>
        <span className="sep">/</span>
        <span>{DOMAIN_LABEL[item.domain] ?? item.domain}</span>
        <span className="sep">/</span>
        <span>{ROMAN[item.ord] ?? item.ord}</span>
      </p>

      {item.image_url ? (
        <figure className={`plate full ${active ? 'dim' : ''}`}>
          <img
            src={mediaUrl(item.image_url) ?? ''}
            alt={item.title_zh}
            referrerPolicy="no-referrer"
          />
        </figure>
      ) : (
        <p className="t-archive plate-missing">
          {MEDIA_MISSING[item.domain] ?? '素材待补'} · {item.title_orig ?? item.title_zh}
        </p>
      )}

      <WallLabel item={item} size="full" />
      <p className="hook lead">{item.hook}</p>
      <p className="t-archive anchor block">{item.anchor.label}</p>

      <div className="itempage-actions">
        <label className="done">
          <input
            type="checkbox"
            checked={Boolean(item.done_at)}
            onChange={(e) => toggle.mutate({ issueId: item.issue_id, ord: item.ord, done: e.target.checked })}
          />
          看完了
        </label>
        <Link className="ghost plain" to={issue ? `/issues/${issue.id}` : '/'}>
          回本期
        </Link>
      </div>

      <section className="evidence-block">
        <h3 className="t-label">出处</h3>
        {item.evidence.map((ev) => (
          <article key={ev.chunk_id} className={`ev ${active === ev.chunk_id ? 'focus' : ''}`}>
            <div className="ev-head">
              <CitationMark
                mark={ev.mark}
                onClick={() => setActive(active === ev.chunk_id ? null : ev.chunk_id)}
              />
              <span className="t-archive ev-source">{ev.source}</span>
            </div>
            <p className="ev-body">{ev.excerpt}</p>
            <div className="t-archive ev-meta">
              <span>{ev.doc_id}</span>
              <span className="sep">·</span>
              <span>rerank {ev.scores.rerank?.toFixed(3) ?? '—'}</span>
            </div>
          </article>
        ))}
      </section>

      <AskPanel item={item} />
    </div>
  );
}
