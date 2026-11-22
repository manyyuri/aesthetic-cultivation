import type { Issue } from '../api/client';

const WEEKDAY = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

export function IssueHeader({ issue }: { issue: Issue }) {
  const date = new Date(`${issue.publish_date}T00:00:00`);
  const done = issue.items.filter((i) => i.done_at).length;
  return (
    <header className="issue-head">
      <div className="eyebrow">
        <span>第 {String(issue.issue_no).padStart(3, '0')} 期</span>
        <span className="sep">·</span>
        <span>
          {issue.publish_date} {WEEKDAY[date.getDay()]}
        </span>
        <span className="sep">·</span>
        <span>今夜 {issue.minutes} 分钟</span>
        <span className="sep">·</span>
        <span>
          完成 {done}/{issue.items.length}
        </span>
        {issue.status === 'partial' ? (
          <>
            <span className="sep">·</span>
            <span className="warn">素材不足 · 本期减配</span>
          </>
        ) : null}
      </div>
      <h1 className="display-1">{issue.title}</h1>
      <p className="issue-sub">{issue.subtitle}</p>
    </header>
  );
}
