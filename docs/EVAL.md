# 评测

## 1. 语料与 golden（诚实说明）

| 项 | 现状 |
|---|---|
| 语料 | 芭蕾 4 份 / 12 chunk；音乐 4 份 / 11 chunk；美术 3 份 / 7 chunk（公有领域摘录，带 `source_url` + license） |
| golden | `eval/golden/ballet.jsonl` 15 条：12 可答（单事实、版本对比）+ 3 不可答（诱导幻觉） |
| 其余领域 | golden 未写。**先做深一个领域，再复制结构**，不铺开 |

`make eval-check` 会校验 golden 里引用的 `doc_id` 真实存在于库中（防止黄金集引用不存在的文档）。

## 2. 指标定义

| 指标 | 定义 | 实现 | 门槛 |
|---|---|---|---|
| recall@k | `must_cite_doc_ids` 被 top-k 覆盖 | 自研纯计算 | ≥ 0.85 |
| MRR | 首个命中 doc 的倒数排名均值 | 自研 | ≥ 0.70 |
| citation_coverage | 答案中"带 `[S#]` 且 id 有效"的句子占比 | 规则 | = 1.00 |
| refusal_accuracy | 不可答样本被正确拒答（且没吐出 `key_facts`） | 规则 | ≥ 0.90 |
| p95 检索延迟 | `retrieve` 端到端 | 自研 | ≤ 800 ms |
| faithfulness / context_precision | 答案是否被证据支持 | Ragas（需 LLM judge） | ≥ 0.90 / ≥ 0.75 —— **当前未评** |

## 3. 当前结果（2026-11-22，ballet，k=5）

```
recall@k           1.000   ✅ (≥0.85)
mrr                0.903   ✅ (≥0.70)
citation_coverage  1.000   ✅ (=1.00)
refusal_accuracy   1.000   ✅ (≥0.90)
p95 latency        385 ms  ✅ (≤800ms)
cases              15
```

运行：`make eval-ci DOMAIN=ballet`（报告写在 `eval/reports/ballet-YYYY-MM-DD.json`）。

**这些数字说明什么、不说明什么**：

- 说明：链路正确 —— 双路召回、RRF、重排、阈值、引用编号、拒答闸门都能在真实文档上工作；
- 说明：3 条不可答样本全部被拒答（年份缺失 / 1990 年后版本 / 票价这类库外问题）；
- **不说明**检索质量：当前 provider 是 `hashed` embedding + `lexical` rerank（离线兜底），语料只有 12 个 chunk。
  小语料下 recall 容易满分，这个数字不可外推到真实库。

## 4. faithfulness 为什么是空的

Ragas 需要 LLM judge。没有 `DEEPSEEK_API_KEY` 时 `run_domain` 会返回
`{"skipped": true, "reason": "缺 DEEPSEEK_API_KEY..."}`，**不伪造分数**。
配好 key 后 `make eval DOMAIN=ballet`（不带 `--ci`）会自动跑 judge，结果写在同一份报告里。

## 5. min_score 校准（未做，勿拍脑袋）

`config.yaml` 里 `lexical: 0.12`、`bge: 0.35` 只是初值。

- 换成 bge-m3 + bge-reranker 后，必须对 `[0.20, 0.65]` 步长 0.05 扫描，
  选"recall@5 掉幅 ≤ 3% 前提下 refusal_accuracy 最高"的点；
- 曲线与表格追加到本文档，然后再改 config；
- 没有扫描数据就调阈值 = 用一个未知换另一个未知。

## 6. 改动记录（每次改检索/评审都必须追加一行）

| 日期 | 改动 | recall@5 | MRR | citation_cov | refusal | 结论 |
|---|---|---|---|---|---|---|
| 2026-11-22 | 初始：hashed + lexical，`max_chunks_per_doc=3`，40 字噪声下限 | 1.000 | 0.903 | 1.000 | 1.000 | 保留（链路基线） |

## 7. bad case 闭环

1. 前端"这件事说错了" 或 `POST /api/eval/feedback` → `eval/feedback/{date}.jsonl`
2. `make eval-feedback` 出三类清单：
   - **缺文档** → 补 raw → `ingest + index`
   - **召不回** → 调 chunker 边界 / 分词 / `recall_pool`，指标不升就回滚
   - **说错** → 先改 reviewer 判据，**不要**先动检索
3. 前端"转 golden" 或 `POST /api/eval/promote {item_id}` 把坏例沉淀成新 golden（标 `needs_review`，需人工确认）
