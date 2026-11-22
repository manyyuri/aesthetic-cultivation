import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Alert, Button, Input, InputNumber, Progress, Select, Statistic, Switch, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { listDocs, listSources, startFetch, getJob } from '../api/kb';
import type { FetchReport, KbDoc, SourceInfo } from '../api/kb';
import { DOMAIN_LABEL } from '../api/client';

const DOMAINS = ['art', 'music', 'ballet'] as const;

function licenseTag(license: string | null) {
  if (!license) return <Tag>未知</Tag>;
  if (license === 'CC0-1.0') return <Tag color="green">{license}</Tag>;
  if (license.toLowerCase().includes('public-domain')) return <Tag color="blue">{license}</Tag>;
  if (license.startsWith('CC-BY')) return <Tag color="gold">{license}</Tag>;
  return <Tag>{license}</Tag>;
}

export function KnowledgeBasePage() {
  const { domain: routeDomain } = useParams();
  const [domain, setDomain] = useState<string>(routeDomain ?? 'art');
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [docs, setDocs] = useState<KbDoc[]>([]);
  const [indexVersion, setIndexVersion] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [limit, setLimit] = useState(10);
  const [query, setQuery] = useState('');
  const [dryRun, setDryRun] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [report, setReport] = useState<FetchReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    const [rows, docPage] = await Promise.all([listSources(), listDocs(domain)]);
    setSources(rows);
    setDocs(docPage.docs);
    setIndexVersion(docPage.index_version);
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain]);

  const domainSources = useMemo(() => sources.filter((s) => s.domain === domain), [sources, domain]);
  useEffect(() => {
    setSource(domainSources[0]?.name ?? null);
  }, [domainSources]);

  // 轮询 job：不引 websocket，抓取是几十秒量级的批量任务
  useEffect(() => {
    if (!jobId) return;
    setProgress(10);
    const timer = window.setInterval(async () => {
      try {
        const job = await getJob(jobId);
        if (job.status === 'done') {
          window.clearInterval(timer);
          setProgress(100);
          setReport(job.report as FetchReport);
          setJobId(null);
          await refresh();
        } else if (job.status === 'failed') {
          window.clearInterval(timer);
          setError(job.error ?? '抓取失败');
          setJobId(null);
        } else {
          setProgress((p) => Math.min(90, p + 12));
        }
      } catch (err) {
        window.clearInterval(timer);
        setError(String(err));
        setJobId(null);
      }
    }, 900);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const columns: ColumnsType<KbDoc> = [
    {
      title: '编号',
      dataIndex: 'doc_id',
      width: 240,
      render: (value: string, row) =>
        row.source_url ? (
          <a className="t-archive" href={row.source_url} target="_blank" rel="noreferrer">
            {value}
          </a>
        ) : (
          <span className="t-archive">{value}</span>
        ),
    },
    { title: '标题', dataIndex: 'title' },
    {
      title: '来源',
      dataIndex: 'source',
      width: 130,
      render: (value: string) => <span className="t-archive">{value}</span>,
    },
    {
      title: '许可',
      dataIndex: 'license',
      width: 170,
      render: (value: string | null) => licenseTag(value),
    },
    {
      title: '抓取时间',
      dataIndex: 'retrieved_at',
      width: 170,
      render: (value: string | null) => <span className="t-archive">{value?.slice(0, 16) ?? '—'}</span>,
    },
    { title: 'chunk', dataIndex: 'chunk_count', width: 80 },
    { title: '优先级', dataIndex: 'source_priority', width: 150 },
  ];

  return (
    <div className="page">
      <header className="issue-head">
        <div className="eyebrow">
          <span>知识库</span>
          <span className="sep">·</span>
          <span>{docs.length} 份文档</span>
          <span className="sep">·</span>
          <span>索引 {indexVersion ?? '未建'}</span>
        </div>
        <h1 className="display-1">语料</h1>
        <p className="issue-sub">
          只收有可核查许可的资料。抓取默认"试跑"，确认映射对了再真写。
        </p>
      </header>

      <section className="kb-panel">
        <div className="kb-row">
          <label className="t-label">领域</label>
          <Select
            value={domain}
            onChange={setDomain}
            style={{ width: 160 }}
            options={DOMAINS.map((d) => ({ value: d, label: DOMAIN_LABEL[d] }))}
          />
          <label className="t-label">数据源</label>
          <Select
            value={source}
            onChange={setSource}
            style={{ width: 260 }}
            placeholder="该领域暂无已注册数据源"
            options={domainSources.map((s) => ({
              value: s.name,
              label: `${s.name} · ${s.license} · 已入库 ${s.doc_count}`,
            }))}
          />
          <label className="t-label">数量</label>
          <InputNumber min={1} max={100} value={limit} onChange={(v) => setLimit(v ?? 10)} />
          <label className="t-label">试跑</label>
          <Switch checked={dryRun} onChange={setDryRun} />
          <Button type="primary" disabled={!source || Boolean(jobId)} onClick={async () => {
            if (!source) return;
            setError(null);
            setReport(null);
            try {
              const { job_id } = await startFetch({
                source,
                limit,
                query: query.trim() || undefined,
                dry_run: dryRun,
              });
              setJobId(job_id);
            } catch (err) {
              setError(String(err));
            }
          }}>
            抓取
          </Button>
        </div>
        <div className="kb-row">
          <label className="t-label">检索词</label>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="留给源的检索关键字（可空）"
            style={{ maxWidth: 380 }}
          />
          {source ? <span className="hint">该源许可：{licenseTag(domainSources.find((s) => s.name === source)?.license ?? null)}</span> : null}
        </div>

        {jobId ? <Progress percent={progress} size="small" status="active" /> : null}
        {error ? <Alert type="error" showIcon message={error} /> : null}

        {report ? (
          <div className="kb-report">
            <Statistic title="写入" value={report.written} />
            <Statistic title="跳过" value={report.skipped} />
            <Statistic title="拒收" value={report.refused.length} />
            <Statistic title="候选" value={report.candidates} />
            {report.dry_run ? <Tag color="gold">试跑，未落盘</Tag> : null}
            {report.refused.length ? (
              <ul className="kb-refused t-archive">
                {report.refused.slice(0, 6).map((item) => (
                  <li key={item.external_id}>
                    {item.external_id} — {item.reason}
                  </li>
                ))}
              </ul>
            ) : null}
            {Object.keys(report.missing_meta).length ? (
              <p className="hint">缺元数据：{JSON.stringify(report.missing_meta)}</p>
            ) : null}
          </div>
        ) : null}
      </section>

      <Table<KbDoc>
        rowKey="doc_id"
        size="small"
        columns={columns}
        dataSource={docs}
        pagination={{ pageSize: 12, hideOnSinglePage: true }}
        locale={{ emptyText: '这个领域还没有文档：先抓取，或把 Markdown 放进 data/raw' }}
      />
    </div>
  );
}
