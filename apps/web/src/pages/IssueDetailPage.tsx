import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useIssue, useToggleDone } from '../api/hooks';
import { SpotlightLayer } from '../components/SpotlightLayer';
import { IssueHeader } from '../components/IssueHeader';
import { RouteRail } from '../components/RouteRail';
import { ItemCard } from '../components/ItemCard';

export function IssueDetailPage() {
  const { issueId } = useParams();
  const { data: issue, isLoading } = useIssue(issueId);
  const toggle = useToggleDone();
  const [current, setCurrent] = useState(1);
  const onSpot = useCallback((ord: number) => setCurrent(ord), []);

  if (isLoading || !issue) return <div className="page"><div className="skeleton-body" /></div>;

  return (
    <>
      <SpotlightLayer onChange={onSpot} />
      <div className="page">
        <p className="crumbs t-archive">
          <Link to="/issues">合订本</Link>
          <span className="sep">/</span>
          <span>{issue.publish_date}</span>
        </p>
        <IssueHeader issue={issue} />
        <div className="issue-body">
          <RouteRail items={issue.items} current={current} />
          <main className="stack">
            {issue.items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                current={current === item.ord}
                onToggleDone={(done) => toggle.mutate({ issueId: issue.id, ord: item.ord, done })}
              />
            ))}
          </main>
        </div>
      </div>
    </>
  );
}
