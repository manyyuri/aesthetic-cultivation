import { useEffect } from 'react';

/**
 * 签名元素：射灯。光源跟随"阅读位置"（视口中心最近的件），不是鼠标。
 * 语义是"你正站在这一件前面"——跟光标就变成屏保了。
 */
export function SpotlightLayer({ onChange }: { onChange?: (ord: number) => void }) {
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let raf = 0;

    const update = () => {
      raf = 0;
      const cards = Array.from(document.querySelectorAll<HTMLElement>('[data-spot]'));
      if (!cards.length) return;
      const mid = window.innerHeight * 0.42;
      let best: HTMLElement | null = null;
      let bestDist = Number.POSITIVE_INFINITY;
      for (const card of cards) {
        const anchor = card.querySelector<HTMLElement>('[data-spot-anchor]') ?? card;
        const rect = anchor.getBoundingClientRect();
        const dist = Math.abs(rect.top + Math.min(rect.height, 140) / 2 - mid);
        if (dist < bestDist) {
          bestDist = dist;
          best = card;
        }
      }
      if (!best) return;
      const anchor = best.querySelector<HTMLElement>('[data-spot-anchor]') ?? best;
      const rect = anchor.getBoundingClientRect();
      const root = document.documentElement;
      // 圆心落在标题左侧，半径刚够罩住展签与第一句，不做大范围泛光
      root.style.setProperty('--sx', `${rect.left + Math.min(rect.width, 440) * 0.26}px`);
      root.style.setProperty('--sy', `${rect.top + 30}px`);
      if (best.dataset.ord) onChange?.(Number(best.dataset.ord));
    };

    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };

    if (!reduce) {
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', onScroll);
    }
    update();
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [onChange]);

  return <div className="spotlight-layer" aria-hidden="true" />;
}
