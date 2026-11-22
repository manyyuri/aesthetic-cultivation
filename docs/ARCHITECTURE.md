# 架构

## 1. 分层与依赖方向

```
web ──(packages/contracts 类型)──▶ api
api ──▶ orchestrator ──▶ curation ──▶ rag ──▶ index/domain/config
                                 └──▶ llm / store / push（port 实现）
```

硬规则：

- `rag` 不 import `curation` / `orchestrator` / `api`
- `curation` 不 import `api`
- `orchestrator` 不 import `httpx` / `chromadb` / `sqlite3` / `smtplib`（只碰 port 与 store）
- `web` 只经生成类型访问后端；`packages/ui` 只放 token 与主题

## 2. 一次「建期」的完整时序

```
cron 05:00
 └─ make issue-build  (cli → orchestrator.build_issue)
     ├─ start_run(kind=issue_build) → Tracer 落 steps
     ├─ curation.build_candidates × 3 领域
     │    · 只收库内真实对象（doc_id 必须存在）
     │    · 排名 = 时间锚 0.4 + 未用天数 0.3 + 元数据完整度 0.2 + 确定性抖动 0.1
     ├─ 对每个候选：
     │    ├─ rag.retrieve(query=标题+小节)  → evidence_status 必须 found
     │    ├─ 校验：候选 doc 必须在召回结果里（否则 evidence_other_doc）
     │    ├─ anchors.build_anchor           → 领域校验器（时长/幕数/cue）
     │    ├─ writer.write                    → 抽取式或 LLM（失败自动回退）
     │    └─ review（evidence / anchor / tone / novelty）
     │         · PASS → 进本期
     │         · REWRITE → 同候选重写一次
     │         · REPLACE → 换下一个候选（总数 ≤ max_rebuild）
     ├─ 组装：ord 连续、证据非空、总时长 ≤ minute_budget
     ├─ 降级链：3 件 ready / 2 件 partial「今夜两幕」/ <2 件 往期回访
     └─ save_issue + finish_run
cron 07:30
 └─ make issue-deliver → push.deliver(inapp|email|macos) → mark_delivered
```

## 3. 为什么首页不是对话框

推送产品的价值是"打开就有一期、20 分钟走完"。

- 对话框首屏是空白 → 用户每天都要自己发起一次，订阅就没有意义；
- 内容的组织单位是**一期**（3 件 + 动线 + 时间预算），不是一次问答；
- 追问是低频动作，只在读完某一件后发生，所以做成件内抽屉并自动带该件证据上下文。

## 4. 索引版本化

```
data/index/{domain}/
├── 2026-11-22.1/{bm25/, vectors/, manifest.json}
├── 2026-11-22.2/...
└── active.json          ← {"index_version": "..."}  原子 os.replace 切换
```

- 检索侧按 `active.json` 的 mtime 热切换，进行中的请求不受影响；
- `manifest.embedding_fingerprint` 与当前 embedder 不一致 → 503，**不静默降级**（换模型必须重建）；
- 回滚 = 改写 active 指针（`make rollback`）；
- 禁止原地追加向量（向量 id 与 chunks 失配是最难查的一类 bug）。

## 5. 缓存

键 = `sha256(domain | norm_query | top_k | sorted_filter | index_version)`。

- 请求级 LRU 512 / TTL 600s；
- 带 `X-Task-Id` 时额外任务级缓存 900s（正面对冲"Agent 同一问题反复检索烧 token"）；
- 负缓存（`insufficient`）同样有效，避免反复撞空库；
- 键里含版本号，换索引自然失效。

## 6. 端口边界（将来换 Go / Java 的唯一改动点）

```python
class RagPort:    retrieve(req) -> RetrieveResponse
class LlmPort:    json(...) / chat(...)   # 结构化 + 普通
class StorePort:  issues / items / runs / steps / feedback
class PushPort:   deliver(issue, channels) -> DeliveryReport
class ClockPort:  ...
```

编排器只依赖这 5 个协议；RAG 与前端一行不改即可替换实现。

## 7. 为什么主路径不用 Multica

见 `multica/README.md`：它的 Skill 是指令包、Agent 跑的是本机编码 CLI、界面是 issue 工单模型。
本产品要的是读者向的流式答案与证据面板。保留为"后台批量考据"的可选接法（MCP），不做半成品。
