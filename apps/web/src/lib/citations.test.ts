import { describe, expect, it } from 'vitest';
import { citedIds, splitCitations } from './citations';

describe('splitCitations', () => {
  it('把 [S1] 切成独立片段', () => {
    expect(splitCitations('甲 [S1]。')).toEqual([
      { kind: 'text', value: '甲 ' },
      { kind: 'cite', id: 'S1' },
      { kind: 'text', value: '。' },
    ]);
  });

  it('没有引用时只有一段文字', () => {
    expect(splitCitations('资料里没有能支撑这个问题的原文。')).toEqual([
      { kind: 'text', value: '资料里没有能支撑这个问题的原文。' },
    ]);
  });

  it('多次调用不共享 lastIndex（全局正则会污染）', () => {
    const first = splitCitations('甲 [S1]。乙 [S2]。');
    const second = splitCitations('甲 [S1]。乙 [S2]。');
    expect(first).toEqual(second);
    expect(citedIds('甲 [S1]。乙 [S2]。甲 [S1]。')).toEqual(['S1', 'S2']);
  });
});
