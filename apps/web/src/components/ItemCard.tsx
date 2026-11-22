import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Item } from '../api/client';
import { DOMAIN_LABEL, ROMAN } from '../api/client';
import { WallLabel } from './WallLabel';
import { CitationMark } from './CitationMark';
import { AskPanel } from './AskPanel';
import { EvidenceDrawer } from './EvidenceDrawer';

export function ItemCard({
  item,
  current,
  onToggleDone,
}: {
  item: Item;
  current: boolean;
  onToggleDone: (done: boolean) => void;
}) {
  const [drawer, setDrawer] = useState(false);
  const [asking, setAsking] = useState(false);
  const mark = item.evidence[0]?.mark ?? '';

  return (
    <article
      id={`item-${item.ord}`}
      data-spot
      data-ord={item.ord}
      className={`item ${item.done_at ? 'done' : ''} ${current ? 'current' : ''}`}
    >
      <div className="item-kicker">
        <span className="t-archive idx">{ROMAN[item.ord] ?? item.ord}</span>
        <span className="t-label dom">{DOMAIN_LABEL[item.domain] ?? item.domain}</span>
        <span className="t-archive no">{String(item.ord).padStart(3, '0')}</span>
      </div>

      <div className={`item-main ${item.image_url ? 'with-plate' : 'plain'}`}>
        {/* 没有图就不摆一个空相框：宁可是一栏文字，也不要一块"待补"骗版面 */}
        {item.image_url ? (
          <figure className="plate">
            <img src={item.image_url} alt={item.title_zh} loading="lazy" />
          </figure>
        ) : null}
        <div>
          <Link to={`/item/${item.id}`} className="label-link">
            <WallLabel item={item} />
          </Link>
          <p className="hook">{item.hook}</p>
        </div>
      </div>

      <div className="item-actions">
        <span className="t-archive anchor">{item.anchor.label}</span>
        <div className="actions">
          {mark ? <CitationMark mark={mark} onClick={() => setDrawer(true)} /> : null}
          <button type="button" className="ghost" onClick={() => setAsking((v) => !v)}>
            {asking ? '收起' : '问一句'}
          </button>
          <label className="done">
            <input
              type="checkbox"
              checked={Boolean(item.done_at)}
              onChange={(e) => onToggleDone(e.target.checked)}
            />
            看完了
          </label>
        </div>
      </div>

      {asking ? <AskPanel item={item} compact /> : null}
      <EvidenceDrawer item={item} open={drawer} onClose={() => setDrawer(false)} />
    </article>
  );
}
