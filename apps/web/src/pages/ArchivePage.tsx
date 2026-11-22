import { Link } from 'react-router-dom';
import type { Issue } from '../api/client';
import { useIssueList } from '../api/hooks';

function weekKey(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00`);
  const first = new Date(d.getFullYear(), 0, 1);
  const week = Math.ceil(((d.getTime() - first.getTime()) / 86400000 + first.getDay() + 1) / 7);
  return `${d.getFullYear()} 年 · 第 ${week} 周`;
}

export function ArchivePage() {
  const { data, isLoading } = useIssueList();
  if (isLoading) return <div className="page"><div className="skeleton-body" /></div>;
  const issues = (data ?? []).filter((i: Issue) => i.status !== 'draft');
  const groups = new Map<string, Issue[]>();
  for (const issue of issues) {
    const key = weekKey(issue.publish_date);
    groups.set(key, [...(groups.get(key) ?? []), issue]);
  }

  return (
    <div className="page">
      <header className="issue-head">
        <div className="eyebrow">
          <span>合订本</span>
          <span className="sep">·</span>
          <span>{issues.length} 期</span>
        </div>
        <h1 className="display-1">往期</h1>
        <p className="issue-sub">按周装订。每期三件，留着可以回看。</p>
      </header>

      {[...groups.entries()].map(([week, list]) => (
        <section key={week} className="arc-group">
          <h2 className="t-label arc-week">{week}</h2>
          {list.map((issue) => {
            const done = issue.items.filter((i) => i.done_at).length;
            const band = issue.items[0]?.domain ?? 'art';
            return (
              <Link key={issue.id} to={`/issues/${issue.id}`} className="arc-row">
                <span className={`arc-band dom-${band}`} aria-hidden="true" />
                <span className="t-archive arc-no">{String(issue.issue_no).padStart(3, '0')}</span>
                <span className="arc-main">
                  <span className="t-display arc-title">{issue.title}</span>
                  <span className="arc-desc">{issue.items.map((i) => i.title_zh).join('、')}</span>
                </span>
                <span className="t-archive arc-meta">
                  {issue.publish_date}
                  <br />
                  {done}/{issue.items.length} 完成
                </span>
              </Link>
            );
          })}
        </section>
      ))}
      {issues.length === 0 ? <p className="drawer-note">还没有往期。先跑 make issue:build。</p> : null}
    </div>
  );
}
