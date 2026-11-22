# 为什么主路径不用 Multica

核实过 [multica-ai/multica](https://github.com/multica-ai/multica)（Go 后端 + TS 前端，可自托管）：

1. 它的 Skill 是**给编码 Agent 复用的指令/步骤包**，不是 HTTP 工具注册；工具接入走 MCP。
2. 它的 Agent 执行的是**你机器上已装好并登录的编码 CLI**，一次 run 是分钟级的 issue 交付流。
3. 它的界面是 issue / project / run 的工单模型，没有面向读者的流式答案、引用高亮与证据面板。

而本产品是"打开就有一期、20 分钟读完、每句可回看原文"的读物。硬套工单模型会把延迟、界面、数据模型三件事同时拧坏。

## 正确用法（可选，未接线）

把 RAG 包成 MCP server，让 Multica 里的编码 Agent 在 issue 里做**异步、批量**的后台考据作业：

- `knowledge_retrieval(domain, query, meta_filter?)` → 薄封装 `POST /api/retrieve`（`api/routes_kb.py` 已暴露该端点，直接复用）
- 一份作业指导书 Skill：先查 → 记来源 → 冲突标存疑 → 交付格式

触发条件：需要"补库/校对/批量考据"这类几十分钟的后台任务时再做，1–2 天工作量。当前版本不接线，因此仓库里只有这份说明，没有半成品代码。
