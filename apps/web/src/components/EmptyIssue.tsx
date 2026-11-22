import { Link } from 'react-router-dom';

export function EmptyIssue({ message, lastIssue }: { message: string; lastIssue?: string | null }) {
  return (
    <div className="page">
      <header className="issue-head">
        <div className="eyebrow">
          <span>今天还没有节目单</span>
        </div>
        <h1 className="display-1">正在排期</h1>
        <p className="issue-sub">{message}</p>
      </header>
      <div className="empty-actions">
        <code className="t-archive">make issue:build</code>
        {lastIssue ? (
          <Link className="ghost" to={`/issues/${lastIssue}`}>
            先看上一期
          </Link>
        ) : null}
      </div>
    </div>
  );
}
