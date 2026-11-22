# 评测

## 1. 语料与 golden

| 领域 | 语料 | golden | 说明 |
|---|---|---|---|
| art | 8 份 / 22 chunk（3 份手写摘录 + 5 份 Met CC0 抓取） | 12 条（9 可答 + 3 不可答） | 含 4 条**中文查询 → 英文条目**的跨语言用例 |
| ballet | 4 份 / 12 chunk（公有领域摘录） | 15 条（12 可答 + 3 不可答） | 时序/版本类问题为主 |
| music | 6 份 / 25 chunk（4 份手写 + 2 份 MusicBrainz） | 未写 | 先做深两个领域，再复制结构 |

`make eval-check DOMAIN=art` 会校验 golden 引用的 `doc_id` 真实存在，防止黄金集引用不存在的文档。

## 2. 指标与门槛（门槛按"谁作答"分开）

| 指标 | 定义 | 实现 |
|---|---|---|
| recall@k | `must_cite_doc_ids` 被 top-k 覆盖 | 纯计算 |
| MRR | 首个命中 doc 的倒数排名均值 | 纯计算 |
| citation_coverage | 带 `[S#]` 且编号有效的句子占比 | 规则 |
| refusal_accuracy | 不可答样本被正确拒答（关键事实没被写成带引用的断言） | 规则 |
| faithfulness | 答案是否只依据证据 | LLM 判官（`prompts/judge.md`，t=0） |

门槛：

```python
stub: {recall 0.85, mrr 0.70, coverage 1.00, refusal 0.90}
llm:  {recall 0.85, mrr 0.70, coverage 0.80, refusal 0.90, faithfulness 0.85}
```

coverage 门槛不同是有原因的：抽取式 stub 只会输出带引用的原文句子（必须满分）；
模型会写"资料里没有…"这类缺口说明，这些句子天然没有引用，1.00 不现实。

## 3. 检索质量：hashed/lexical → bge-m3 + bge-reranker（与作答无关，可复现）

`make eval-ci`（`--ci` 固定用抽取式作答，离线、可复现）：

| 领域 | 配置 | recall@5 | MRR |
|---|---|---|---|
| art | hashed 1024 + lexical | 0.556 | 0.481 |
| art | **bge-m3 1024 + bge-reranker-v2-m3** | **1.000** | **0.889** |
| ballet | hashed + lexical | 1.000 | 0.826 |
| ballet | **bge-m3 + bge-reranker-v2-m3** | **1.000** | **0.944** |

art 的 0.556 → 1.000 主要来自四条**中文查询打英文条目**的用例（`art_001`–`art_004`）：
`hashed` 只能字面匹配，跨语言全灭（4 条全部 `insufficient`）；`bge-m3` 是 multilingual，直接命中。

## 4. 跨语言：具体到 query

| query | hashed | bge-m3 |
|---|---|---|
| 古希腊晚期的壁画湿壁画 | ❌ insufficient | ✅ `met_256186`（Wall painting, Fresco, Late Classical） |
| 清代的中国画册 纸本水墨 | ❌ insufficient | ✅ `met_51776` |
| 十八世纪英国的雕版印刷讽刺画 | ❌ insufficient | ✅ `met_670172`（Stipple engraving, 1784） |
| 卢浮宫收藏的德拉克洛瓦油画（不可答） | ✅ 拒答 | ✅ 拒答 |

## 5. 端到端（本次会话实测，LLM 作答）

> ⚠️ 这两行是 2026-11-22 实测产出（DeepSeek `deepseek-flash`）。**之后该 key 返回 402 Insufficient Balance**，
> 现在重跑会退化成"stub 兜底 + 判官跳过"。充值后 `make eval DOMAIN=art` 可复现。

| 领域 | recall@5 | MRR | coverage | refusal | faithfulness (n) |
|---|---|---|---|---|---|
| art | 1.000 | 0.889 | 0.811 | 1.000 | **0.889** (9) |
| ballet | 1.000 | 0.944 | 0.824 | 1.000 | **0.833** (11) |

判官判为"无据"的典型是**作品名**：一开始证据里只传 chunk 文本，不含文档标题，
模型无法核对《星月夜》这个标题 ⇒ 判无据。修法是把 `doc_title` 一起放进证据（产品侧修复，不是改判据）。
仍然存在的真实问题：把两份文档的描述合并成同一件作品的连续叙述（`art_007`），属于轻度推断。

## 6. 离线端到端（CI 基线，可复现）

`make eval-ci DOMAIN=ballet`：recall 1.000 / MRR 0.944 / coverage **1.000** / refusal 1.000。

`make eval-ci DOMAIN=art`：recall 1.000 / MRR 0.889 / coverage **0.444** / refusal 1.000。

art 的 coverage 0.444 是**已知且预期**的：检索已经跨语言，但抽取式 stub 不会翻译/组织，
中文问题遇到英文原文就拒答（宁可拒答，不要沾边就算）。这也是为什么"接真模型"不是可选项。

## 7. min_score 校准（2026-11-22，`scripts/calibrate.py`）

规则：`recall@5` 掉幅 ≤ 3% 的前提下，取拒答最准的点；同分取更保守（更小）的阈值。

**bge-reranker-v2-m3**（默认）：

| min_score | art recall | art refusal | ballet recall | ballet refusal |
|---|---|---|---|---|
| 0.15 | 1.000 | 1.000 | 1.000 | 1.000 |
| 0.35 | 1.000 | 1.000 | 1.000 | 1.000 |
| 0.50 | 1.000 | 1.000 | 1.000 | 1.000 |
| 0.60 | 1.000 | 1.000 | 1.000 | 1.000 |

0.35–0.60 全都满分 ⇒ 取 **0.35**（语料只有 22/12 个 chunk，不把阈值压在样本边界上）。
报告：`eval/reports/calibration-{art,ballet}-*.json`。

**mmarco-mMiniLMv2**（轻量替代，470MB，多语言但中文精确匹配弱）：

| min_score | art recall | ballet recall |
|---|---|---|
| 0.05–0.15 | 0.889 | 1.000 |
| 0.20+ | 0.778 | 0.917 |

它在 `《舞姬》的首演年份与编舞家` 上把天鹅湖排到了第一（bge-reranker 排对）⇒ **不推荐做默认**，
保留为省资源的选项，阈值 `bge:mmarco: 0.15`。

阈值按**具体模型**取值（`config.yaml` 的 `min_score` 支持 `bge:<模型目录名>`），因为不同 cross-encoder 的分数量纲完全不同。

## 8. 冷启动与延迟

| 项 | 数值 |
|---|---|
| bge-m3 首次加载（mps） | ≈ 10 s |
| bge-reranker-v2-m3 首次加载 | ≈ 8 s |
| 稳态检索 p95（含 embed + rerank） | **0.5–1.9 s** |
| 稳态检索 p95（hashed + lexical） | 0.39 s |

`get_embedder()/get_reranker()` 已加 `lru_cache`：不缓存时每次 `Retriever()` 都会重新加载模型，
p95 会从 0.6 s 变成 5 s（这是实测踩到的）。

## 9. 判官（judge）的可信度

- 同一份答案，judge 会在"合并推断""称谓越界"这类**文风问题**上摇摆 —— 已在 `judge.md` 里显式放行同义改写、
  允许 `section` 字段提供标题、允许拒答句；
- n=9/11 太小，**看趋势不看绝对值**；语料扩到 100+ 再谈统计意义；
- judge 用同一家的模型有自我偏好，换模型复测是后续工作。

## 10. 改动记录

| 日期 | 改动 | 结果 | 结论 |
|---|---|---|---|
| 2026-11-22 | 初始：hashed + lexical | recall 1.000 / MRR 0.903 / coverage 1.000 / refusal 1.000（ballet） | 链路基线 |
| 2026-11-22 | 指标 bug：证据为空时答案串是空串，被算成"未拒答" | refusal 0.333 → 1.000 | 保留 |
| 2026-11-22 | 证据带上 `doc_title`；judge 换专门 prompt；`refused()` 按小句判否定作用域 | art coverage 0.44→0.81（LLM），faithfulness 0.56→0.89 | 保留 |
| 2026-11-22 | bge-m3 + bge-reranker-v2-m3，阈值 0.35 | art recall 0.556→1.000；ballet MRR 0.826→0.944 | 保留（默认） |
| 2026-11-22 | `get_embedder/get_reranker` 加缓存 | p95 5.0s → 0.6s | 保留 |
| 2026-11-22 | cache key 纳入 `options` | 校准脚本此前扫阈值无效 | 保留 |

## 11. 下一步

1. 充值后复现 §5，并把 n 扩到 40（art 20 / ballet 20）；
2. 给 music 写 golden（现在有 MusicBrainz 的精确时长，可测"听哪一段"的锚点正确性）；
3. 换一家 judge 交叉验证 faithfulness；
4. 语料过 500 chunk 后重扫阈值，并把结果写死进 `config.yaml`。
