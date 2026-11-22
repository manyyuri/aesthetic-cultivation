/**
 * 设计 token —— 方向：私人策展人的印刷品（美术馆展签 + 音乐会节目册）
 *
 * 三条不可违反的规矩（见 packages/ui/README.md）：
 *  1. 中文标题只用宋体，不拿黑体做标题。
 *  2. 任何编号 / 年份 / 时长 / 馆藏号 / Op. 必须 mono + tabular-nums + letter-spacing .04em。
 *  3. 拉丁原名一律斜体 serif，紧跟中文标题下方、小一号、颜色 inkSoft。
 */

export const color = {
  /** 纸面。冷灰白，刻意避开奶油色 #F4F1EA */
  paper: '#EDEDEA',
  /** 动线栏 / 分隔区底色 */
  paperDeep: '#E4E4DF',
  /** 正文与标题 */
  ink: '#12120F',
  /** 次级正文（开场白、看点句的次句） */
  inkSoft: '#3A3A34',
  /** 元数据、展签行、来源、弃用态 */
  grayInk: '#6B6B63',
  /** 唯一强调色：射灯 + 引用编号。全站只此一处彩色强调 */
  spotlight: '#F0C24B',
  /** 交界线（比 paperDeep 深一档，用于 1px 分隔） */
  rule: '#D3D3CC',
  /** 音乐：乐章 / 乐团 / 唱片 */
  music: '#243B53',
  /** 芭蕾：幕次 / 编舞版本 */
  ballet: '#8C1D2C',
} as const;

export const domain = {
  art: { accent: color.ink, tint: color.spotlight, label: '美术馆' },
  music: { accent: color.music, tint: color.music, label: '音乐会' },
  ballet: { accent: color.ballet, tint: color.ballet, label: '芭蕾' },
} as const;

export type Domain = keyof typeof domain;

export const font = {
  /** 展示 / 中文标题 / 作品名 */
  display: '"Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif',
  /** 拉丁原名（斜体使用） */
  latin: '"Iowan Old Style", "Hoefler Text", Georgia, serif',
  /** 正文 */
  body: '"PingFang SC", "Helvetica Neue", system-ui, sans-serif',
  /** 编号 / 年份 / 时长 / 馆藏号 / 档案 */
  archive: '"SF Mono", "JetBrains Mono", ui-monospace, monospace',
} as const;

/** 字号 / 行高 / 字重 / 字距。px 为单位，直接写进 CSS */
export const type = {
  /** 首页大标题「今夜三幕」 */
  display1: { size: 36, line: 1.15, weight: 400, tracking: '-0.02em' },
  /** 期详情页 / 合订本标题 */
  display2: { size: 26, line: 1.25, weight: 400, tracking: '-0.015em' },
  /** 单件标题（作品名） */
  itemTitle: { size: 22, line: 1.3, weight: 400, tracking: '-0.01em' },
  /** 拉丁原名 */
  latin: { size: 15, line: 1.5, weight: 400, tracking: '0', italic: true },
  /** 正文（看点 / 考据） */
  body: { size: 15, line: 1.85, weight: 400, tracking: '0' },
  /** 正文次级 */
  bodySm: { size: 14, line: 1.8, weight: 400, tracking: '0' },
  /** 眉毛行 / 章节标签（museum section label） */
  label: { size: 11, line: 1.4, weight: 500, tracking: '0.14em', uppercase: true },
  /** 展签元数据行、来源行、№ 编号 */
  meta: { size: 12, line: 1.6, weight: 400, tracking: '0.04em' },
  /** 极小注（连续天数、页脚） */
  micro: { size: 11, line: 1.5, weight: 400, tracking: '0.02em' },
} as const;

/** 4px 基数。刊物式留白：段落之间靠 8 的倍数，区块之间 48/72 */
export const space = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  xxxl: 72,
} as const;

/** 展签是直角；只有可点控件给 2px，避免"卡片化" */
export const radius = { card: 0, control: 2, pill: 999 } as const;

/** 正文行宽上限：刊物式窄栏，超过就是资讯流手感 */
export const measure = { tight: '26em', body: '34em', wide: '46em' } as const;

export const motion = {
  /** 开卷动效总时长（全站唯一的入场序列） */
  openDurationMs: 700,
  /** 标题逐行错位 */
  openStaggerMs: 80,
  /** 射灯跟随（CSS 过渡）；reduced-motion 下为 0 */
  spotFollowMs: 400,
  easing: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
} as const;

/** 左栏动线宽度；<720px 折叠为顶部横排 */
export const layout = { railWidth: 96, pageMaxWidth: 1080, gutter: 24 } as const;

/** 焦点环：2px ink 外描边，永不 outline:none */
export const focusRing = `2px solid ${color.ink}`;

/** antd 6 ConfigProvider theme 映射：antd 只管控件，气质靠自研 CSS */
export const antdTheme = {
  token: {
    colorPrimary: color.ink,
    colorText: color.ink,
    colorTextSecondary: color.inkSoft,
    colorBgBase: color.paper,
    colorBgContainer: color.paper,
    colorBorder: color.rule,
    colorBorderSecondary: color.rule,
    borderRadius: radius.control,
    borderRadiusLG: radius.card,
    boxShadow: 'none',
    boxShadowSecondary: 'none',
    fontFamily: font.body,
    fontSize: 14,
    controlHeight: 36,
    motionDurationMid: '0.2s',
  },
  components: {
    Button: { primaryShadow: 'none', defaultShadow: 'none' },
    Drawer: { paddingLG: 32 },
    Modal: { borderRadiusLG: radius.card },
    Table: { headerBg: color.paper, rowHoverBg: color.paperDeep, borderColor: color.rule },
  },
} as const;

/** 生成 CSS 变量，供 tokens.css / 组件内 var(--…) 使用 */
export function cssVars(): Record<string, string> {
  return {
    '--c-paper': color.paper,
    '--c-paper-deep': color.paperDeep,
    '--c-ink': color.ink,
    '--c-ink-soft': color.inkSoft,
    '--c-gray-ink': color.grayInk,
    '--c-spotlight': color.spotlight,
    '--c-rule': color.rule,
    '--c-music': color.music,
    '--c-ballet': color.ballet,
    '--f-display': font.display,
    '--f-latin': font.latin,
    '--f-body': font.body,
    '--f-archive': font.archive,
    '--measure-body': measure.body,
    '--rail-width': `${layout.railWidth}px`,
    '--page-max': `${layout.pageMaxWidth}px`,
    '--gutter': `${layout.gutter}px`,
    '--open-duration': `${motion.openDurationMs}ms`,
    '--spot-follow': `${motion.spotFollowMs}ms`,
    '--ease': motion.easing,
  };
}
