# @ac/ui · 设计 token

## 方向

**私人策展人的印刷品。** 界面语法来自两件真实的东西：美术馆的展签（wall label）和音乐会的节目册（program book）。不是暗色仪表盘，不是杂志大标题，不是"AI 产品"的常见皮肤。

纸是底色，灯是唯一的强调与唯一的动效。主题自带这两样东西，不需要额外装饰。

## 三条字体规矩（违反即返工）

1. **中文标题只用宋体**（`--f-display`），不拿黑体做标题。展签就是这么排的。
2. **任何编号 / 年份 / 时长 / 馆藏号 / Op. / № 必须等宽**（`.t-archive`：mono + `tabular-nums` + `.04em` 字距）。混排数字用比例字宽会立刻失去"档案感"。
3. **拉丁原名一律斜体 serif**（`.t-latin`），紧跟中文标题下方、小一号、颜色 `--c-ink-soft`。例：

```
印象·日出
Impression, Sunrise
布面油画 · 1872 · 玛摩丹莫奈美术馆
```

## 用色纪律

- `--c-ink` 只用于标题与正文；`--c-gray-ink` 用于元数据、来源、弃用态。
- `--c-spotlight` 是全站唯一的强调色，只允许出现在两处：**射灯**、**引用编号 `№`**。别拿它做按钮、标签、徽章。
- `--c-music` / `--c-ballet` 只在对应领域的小标签与幕次/乐章编号上使用；美术不加色（它有自己的图像）。
- 不引渐变、不引阴影、不引圆角卡片（`radius.card = 0`）。只有可点控件给 2px。

## 唯一的 boldness：射灯

```css
.spotlight-layer {
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(600px circle at var(--sx) var(--sy),
              rgb(240 194 75 / 10%), transparent 62%);
  transition: background-position var(--spot-follow) var(--ease);
}
```

- 光源跟随**阅读位置**（视口中心最近的 `ItemCard` 标题锚点），不是光标——它的语义是"你正站在这一件前面"。
- 鼠标只做 ±24px 微偏移；移动端不跟鼠标。
- `prefers-reduced-motion: reduce` 时固定在当前件，不移动。
- 除射灯与开卷序列（`.open-seq`）之外，不给任何元素加入场动效。

## 与 antd 6 的关系

antd 只管控件（Input / Button / Drawer / Modal / Table / Progress / Segmented / Tag / Statistic），气质全部自研 CSS。主题走 `tokens.ts` 的 `antdTheme`：`colorPrimary = ink`、`borderRadius = 2`、`boxShadow = none`。

写任何 antd 组件前先查真实 API：

```bash
antd info Drawer --format json
antd demo Drawer basic --format json
```

## 同步约定

`src/tokens.ts`（TypeScript 侧）与 `src/tokens.css`（CSS 侧）是同一组值的两份镜像。改一处必须改另一处，`make check` 里的 `scripts/check_tokens.py` 会比对 `--c-*` 变量集合，不一致就红。
