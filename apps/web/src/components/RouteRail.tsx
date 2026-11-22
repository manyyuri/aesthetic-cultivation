import type { Item } from '../api/client';
import { DOMAIN_LABEL, ROMAN } from '../api/client';

/** 左侧动线：序号是真的序列（展厅动线 / 乐章顺序 / 幕次），不是装饰。 */
export function RouteRail({ items, current }: { items: Item[]; current: number }) {
  const done = items.filter((i) => i.done_at).length;
  const pct = items.length ? Math.round((done / items.length) * 100) : 0;
  return (
    <nav className="rail" aria-label="本期动线">
      {items.map((item) => (
        <a
          key={item.id}
          href={`#item-${item.ord}`}
          className={`rail-item ${current === item.ord ? 'on' : ''} ${item.done_at ? 'done' : ''}`}
          aria-current={current === item.ord ? 'true' : undefined}
          aria-label={`${ROMAN[item.ord] ?? item.ord} ${DOMAIN_LABEL[item.domain] ?? item.domain}`}
        >
          <span className="num">{ROMAN[item.ord] ?? item.ord}</span>
          <span className="dom">{DOMAIN_LABEL[item.domain] ?? item.domain}</span>
          <span className="tick" aria-hidden="true">
            ✓
          </span>
        </a>
      ))}
      <div className="rail-bar" aria-hidden="true">
        <i style={{ width: `${pct}%` }} />
      </div>
      <div className="rail-count t-archive" aria-label={`已完成 ${done} 件，共 ${items.length} 件`}>
        {done}/{items.length}
      </div>
    </nav>
  );
}
