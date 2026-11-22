import { Drawer } from 'antd';
import type { Item } from '../api/client';

export function EvidenceDrawer({
  item,
  open,
  focus,
  onClose,
}: {
  item: Item;
  open: boolean;
  focus?: string | null;
  onClose: () => void;
}) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="right"
      size={520}
      title={<span className="t-archive drawer-title">出处 · {item.title_zh}</span>}
    >
      <p className="drawer-note">这里的每一段都是原文，编号对应展签上的 № 编号。</p>
      {item.evidence.map((ev) => (
        <article
          key={ev.chunk_id}
          id={`ev-${ev.chunk_id}`}
          className={`ev ${focus === ev.chunk_id ? 'focus' : ''}`}
        >
          <div className="ev-head">
            <span className="t-archive ev-mark">{ev.mark}</span>
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
      {item.evidence.length === 0 ? <p className="drawer-note">这一件没有挂出处，不该出现在正片里。</p> : null}
    </Drawer>
  );
}
