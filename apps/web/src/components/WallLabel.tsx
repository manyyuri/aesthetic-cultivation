import type { Item } from '../api/client';

/** 展签：中文标题（宋体）+ 原名（斜体 serif）+ mono 元数据行 */
export function WallLabel({ item, size = 'card' }: { item: Item; size?: 'card' | 'full' }) {
  return (
    <div className={`wall-label ${size}`} data-spot-anchor>
      <h2 className="t-display item-title">{item.title_zh}</h2>
      {item.title_orig && item.title_orig !== item.title_zh.replace(/[《》]/g, '').trim() ? (
        <p className="t-latin item-orig">{item.title_orig}</p>
      ) : null}
      <p className="t-archive meta-row">{item.meta_lines.map((m) => m.v).join(' · ')}</p>
    </div>
  );
}
