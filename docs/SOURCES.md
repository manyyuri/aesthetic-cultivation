# 开放数据源

只接有**可核查许可**的来源。`make probe SOURCE=…` 先看一条样本，`make fetch` 才真写。

```bash
make sources                              # 源清单 + 许可 + 已入库文档数
make probe SOURCE=met                     # 只打一条样本，默认不落盘
make fetch SOURCE=met LIMIT=20 DRY=1      # 试跑
make fetch SOURCE=met LIMIT=20            # 真写进 data/raw/art
make ingest DOMAIN=art && make index DOMAIN=art
```

## 源清单

| 源 | 领域 | 许可 | 限速 | 给什么 | 保真度 | 状态 |
|---|---|---|---|---|---|---|
| `met` | art | CC0-1.0 | 2 rps | 作品元数据（年代/材质/技法/分类/馆藏号）+ CC0 图 | **高**：字段直取，只收 `isPublicDomain=true` | 已接 |
| `musicbrainz` | music | CC0-1.0（元数据） | 1 rps（官方硬性） | 曲目结构 + 音轨时长 → 精确"听哪一段" | **高**：时长来自音轨，不估算 | 已接 |
| `internet_archive` | ballet | 逐条人工声明 | 1 rps | 19 世纪论著/节目册全文（`_djvu.txt`） | **低**：论著没有幕数，`acts` 按配置推定 | 机制已接，`identifiers` 需人工填 |

## 三道硬闸门（在 `write_doc` 里，任何 fetcher 都绕不过）

1. **license**：不在 `config/sources.yaml` 的 `allow.licenses` 里 ⇒ 抛 `LicenseRefused`，一个字节都不写；
2. **source_url**：缺失 ⇒ 拒绝（展签上的出处必须可点开）；
3. **require_meta**：缺领域必填字段 ⇒ `missing_meta:<字段>`，进 `FetchReport.missing_meta`。

入库时再补一道：`license` 缺失的文档直接 `docs_rejected`，不计入语料。

## 踩过的坑（都是真实发生的）

### Met 的搜索端点退役了
`/public/collection/v1/search` 于 **2026-10-01 退役**，返回 `410` 并提示改用 `/public/collection/v1.1/search`（Elasticsearch 后端）。
**而且 v1.1 不保证遵守 `isPublicDomain=true`**：实测 `q=monet` 的前 20 条里大部分 `isPublicDomain=false`。
所以：搜索走 v1.1、按 10 倍取样、逐条在详情里复核，宁可多请求几次。实测 50 个候选 → 5 件可用（约 10%）。

### MusicBrainz 没有 UA 会 403
必须带含联系方式的 `User-Agent`，且 **1 req/s**。`SOURCES_UA_CONTACT` 没配时 `make fetch` 直接拒绝运行，
而不是发一个 `no-contact` 的 UA 去赌对方不封。

### 音轨时长才是真相
以前音乐锚点是 `duration_s / 乐章数` 等比估算（`approx: true`）。
MusicBrainz 的每条 track 自带 `length`，所以现在锚点是 `听第二乐章 · 09:36–12:36`（`approx: false`），
`movement_from_s` 由前面各轨累加得出。缺 `length` 的 release 整条拒收——没有时长就做不出"听哪一段"。

### Internet Archive 判定不了公版
19 世纪的扫描件（如 Blasis《The Code of Terpsichore》1830）通常 **没有 `licenseurl` 字段**，
公版状态来自出版年份而不是许可字段。所以这一路**不自动判定**：只接受人工挑过的 `identifiers`，
由人写 `license` 与领域元数据；fetcher 只做搬运，并检查是否存在**相冲突**的许可（如 CC-BY-NC ⇒ 拒）。

### 图不能直连：浏览器拿 403，curl 拿 200
Met 的图床对浏览器热链返回 403（同一 URL 用 curl 200）。展签不能因为图挂了就空一块，
所以加了 `GET /api/media?src=…`：

- 只代理 `sources.yaml` 里 `media_hosts` 声明的域名（防 SSRF），非 https 或未授权域名直接 400；
- 首次取图后缓存到 `data/media/<sha1>`，之后同源直出（`Cache-Control: max-age=604800`）；
- 前端 `<img>` 统一走代理并带 `referrerPolicy="no-referrer"`。

### 中文查询检索英文语料会 `insufficient`
这是离线 provider 的固有限制：`hashed` 向量 + `lexical` 重排只能字面匹配，跨不了语言。
`ask Q="梵高 自画像"` 查 Met 的英文条目会返回资料不足；`ask Q="Self-Portrait with a Straw Hat"` 正常。
接 `bge-m3`（多语言）后可解，见 `docs/EVAL.md` 的下一步。

### 同一小节跨文档重复不等于重复内容
抓来的"形制与分类"这类结构化段落，不同作品之间高度相似（都是"部门/分类/时期"）。
原先的跨文档 `content_hash` 去重会把它们当重复丢掉 → 改为**只对 ≥120 字的段落做跨文档去重**，
短的结构化字段保留；检索层仍有 content_hash 去重兜底。

## 新增一个源

1. `config/sources.yaml` 加一条（`license` 必须在白名单里，`require_meta` 必须覆盖领域必填项，否则启动即失败）；
2. `apps/api/src/ac_api/rag/ingest/sources/<name>.py` 实现 `fetch(limit, query, dry_run) -> FetchReport`，
   落盘只调用 `write_doc`；
3. 在 `sources/__init__.py` 的 `FETCHERS` 里注册；
4. `tests/fixtures/sources/` 放一份录制响应，写单测（零网络）；
5. 本文件的表格补一行。

## 不做

网页 HTML 爬虫（反爬 + 页面改版会让出处失效）、Z-Library / Anna's Archive 一类影子图书馆
（盗版来源写不出 license，整条证据链作废）、OCR、音频下载（只引用链接）、自动扩源发现。
