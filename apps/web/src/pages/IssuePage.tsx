import { useCallback, useState } from 'react';
import type { Issue } from '../api/client';
import { useTodayIssue, useToggleDone } from '../api/hooks';
import { SpotlightLayer } from '../components/SpotlightLayer';
import { IssueHeader } from '../components/IssueHeader';
import { RouteRail } from '../components/RouteRail';
import { ItemCard } from '../components/ItemCard';
import { EmptyIssue } from '../components/EmptyIssue';

export function IssuePage() {
  const { data, isLoading, error } = useTodayIssue();
  const toggle = useToggleDone();
  const [current, setCurrent] = useState(1);
  const onSpot = useCallback((ord: number) => setCurrent(ord), []);

  if (isLoading) {
    return (
      <div className="page">
        <div className="skeleton-head" />
        <div className="skeleton-body" />
      </div>
    );
  }
  if (error || !data) {
    return <EmptyIssue message="连不上后端。先跑 make dev，或者检查 8710 端口。" />;
  }
  if (data.status === 202) {
    const body = data.body as { message: string; last_issue?: string | null };
    return <EmptyIssue message={body.message} lastIssue={body.last_issue} />;
  }

  const issue = data.body as Issue;
  return (
    <>
      <SpotlightLayer onChange={onSpot} />
      <div className="page">
        <IssueHeader issue={issue} />
        <div className="issue-body">
          <RouteRail items={issue.items} current={current} />
          <main className="stack">
            {issue.items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                current={current === item.ord}
                onToggleDone={(done) =>
                  toggle.mutate({ issueId: issue.id, ord: item.ord, done })
                }
              />
            ))}
          </main>
        </div>
        <footer className="issue-foot t-archive">
          <span>每期三件 · 每句都有出处</span>
          <span className="sep">·</span>
          <span>点 № 编号可回看原文</span>
        </footer>
      </div>
    </>
  );
}
