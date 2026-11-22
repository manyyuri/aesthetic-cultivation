# aesthetic-cultivation · 私人节目单

一个私人策展人：**每天（或每周）替你排一期「三幕」——一幅画、一段音乐、一幕芭蕾。**
每件一件一句看点、一个可执行的入口（看这几笔 / 听 03:12–06:40 / 看第二幕），一个确凿出处。20 分钟走完。

不是问答机器人，也不是资讯流：**首页就是这一期**，打开即读；对话只在"看完还想再问一句"时出现，且自动带上这一件的证据。

```
第 001 期 · 2026-11-22 周日 · 今夜 20 分钟 · 完成 0/3
今 夜 三 幕
《星月夜》、勃拉姆斯《第四交响曲》、《胡桃夹子》
────────────────────────────────────────────────
Ⅰ │  Ⅰ 美术馆                                      001
Ⅱ │  夜空被写成旋涡：星与月各有自己的光晕…
Ⅲ │  The Starry Night
   │  oil on canvas · 布面油画 · 后印象派 · 纽约现代艺术博物馆
0/3│  看点：夜空被写成旋涡，柏树像一团黑色的火从前景升起。
   │  看这几处：星与月各有自己的光晕    №001  [问一句]  ☐ 看完了
```

左侧是真实的**动线**（展厅顺序 / 乐章顺序 / 幕次），序号不是装饰。
`№001` 是引用编号——点开是原文、页码、命中分数。**每一句都有出处，没有出处的一件不进正片。**

## 快速开始

```bash
make install                      # 后端 venv + 前端依赖
cp .env.example .env              # 没有 key 也能跑：自动降级为离线 provider
make seed                         # 把公有领域摘录灌进 data/raw
make ingest DOMAIN=ballet && make index DOMAIN=ballet
make issue-build                  # 生成今天这一期
make dev                          # api :8710 + web :5173
```

`make ask Q="《胡桃夹子》首演年份与剧院" DOMAIN=ballet` 可以不看界面直接验检索。
`make eval-ci` 跑免 LLM 的四项指标（见 `docs/EVAL.md`）。

## 架构

| 层 | 做什么 | 边界 |
|---|---|---|
| `apps/api/rag` | 入库、领域分块、BM25+向量双路召回、RRF、重排、元数据过滤、版本化索引 | 换 embedding / 向量库不影响上层 |
| `apps/api/curation` | 选题 → 检索 → 挑件 → 锚点 → 写作 → 评审 → 降级 → 组装 | 规则硬闸门，不靠提示词自觉 |
| `apps/api/orchestrator` | run / step 追踪、建期、推送、追问（SSE） | 只依赖 5 个 port，可换语言 |
| `apps/web` | 一期 / 合订本 / 单件 / 订阅；射灯、展签、证据抽屉 | 只经 `packages/contracts` 访问后端 |

契约由 FastAPI OpenAPI 生成到 `packages/contracts`，`make check` 会拦住 drift。

## 实测指标（`make eval-ci DOMAIN=ballet`，15 条 golden：12 可答 + 3 不可答）

| 指标 | 结果 | 门槛 |
|---|---|---|
| recall@5 | **1.000** | ≥ 0.85 |
| MRR | **0.903** | ≥ 0.70 |
| citation_coverage | **1.000** | = 1.00 |
| refusal_accuracy | **1.000** | ≥ 0.90 |
| p95 检索延迟 | **385 ms** | ≤ 800 ms |

语料规模诚实说明：4 份芭蕾档案 / 12 个 chunk，离线 `hashed` embedding + `lexical` rerank。
这是**链路正确性**的证据，不是检索质量的证据。接真模型后必须重跑并重新校准阈值，见 `docs/EVAL.md`。

## 六个关键判断

1. **推送产品的首页必须有内容** → 生成在用户打开之前跑完（cron 05:00 预跑，07:30 推送），`202 building` 也绝不空白。
2. **评审不过就换候选，不给用户半成品** → 3 件齐 `ready`，2 件「今夜两幕」并记 `coverage_gap`，不足 2 件改发往期回访。
3. **动作锚点校验器是"模拟体验"的底线** → 没有曲目时长就说不出"听 03:12–06:40"，没有幕数就说不出"看第二幕"；缺元数据是换候选，不是降级。
4. **话题只能来自库内真实对象**（必带 `doc_id`）→ 让模型"想个主题"必编。
5. **引用渲染成展签编号 `№001`**，不渲染成蓝色角标 → 溯源是展签语法的一部分，不是 UI 噪音。
6. **不引 Agent 框架** → 规则很窄但很硬（检索预算、冲突仲裁、拒答优先），400 行自研状态机的 trace 完全可解释。

## 目录

```
apps/api/          Python 3.12 + FastAPI：rag / curation / orchestrator / push / eval / store
apps/web/          React 19 + Vite + antd 6：一期 / 合订本 / 单件 / 订阅
packages/ui/       设计 token（纸 + 灯）与字体规则
packages/contracts/ OpenAPI 生成的 TS 类型 + SSE 事件协议
eval/golden/       检索 golden（人工标注）
docs/              ARCHITECTURE / RUNBOOK / EVAL / DECISIONS
multica/           为什么主路径不用 Multica（可选 MCP 接法）
```

## Backlog（明确不做）

多租户/RBAC、Multica 主干化、OCR 训练、Milvus 集群、Celery/Redis、微调 embedding/reranker、自动爬虫、PDF 阅读器、GraphRAG、i18n、移动端 App、积分等级、LLM 自动生成 golden。

## 文案规则

第二人称、句子短、**不用营销词**（震撼/绝美/必看/天花板）、不写"据说"。
按钮说清结果："看完了"而不是"提交"，"问一句"而不是"AI 对话"。空态是邀请，不是安慰。错误说清发生了什么、怎么改。
