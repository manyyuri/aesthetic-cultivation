import { useEffect, useState } from 'react';
import { Segmented } from 'antd';
import { useSaveSubscription, useSubscription, useTestPush } from '../api/hooks';

const CHANNELS = [
  { key: 'inapp', label: '站内' },
  { key: 'email', label: '邮件' },
  { key: 'macos', label: 'macOS 通知' },
];

export function SubscribePage() {
  const { data, isLoading } = useSubscription();
  const save = useSaveSubscription();
  const test = useTestPush();
  const [kind, setKind] = useState<'daily' | 'weekly'>('daily');
  const [time, setTime] = useState('07:30');
  const [channels, setChannels] = useState<string[]>(['inapp']);

  useEffect(() => {
    if (!data) return;
    setKind(data.kind);
    setTime(data.time_of_day);
    setChannels(data.channels);
  }, [data]);

  if (isLoading) return <div className="page"><div className="skeleton-body" /></div>;

  return (
    <div className="page narrow">
      <header className="issue-head">
        <div className="eyebrow">
          <span>订阅</span>
          <span className="sep">·</span>
          <span>连续 {data?.streak ?? 0} 天</span>
        </div>
        <h1 className="display-1">怎么收到节目单</h1>
        <p className="issue-sub">每天一期三件，或每周日一期加长版。改完点保存，第二天按新时间发。</p>
      </header>

      <section className="form-block">
        <label className="t-label">频率</label>
        <Segmented
          value={kind}
          onChange={(v) => setKind(v as 'daily' | 'weekly')}
          options={[
            { label: '每日 · 20 分钟', value: 'daily' },
            { label: '每周日 · 60 分钟', value: 'weekly' },
          ]}
        />
      </section>

      <section className="form-block">
        <label className="t-label" htmlFor="time">
          时间段
        </label>
        <input
          id="time"
          className="ask-input short"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          placeholder="07:30"
        />
        <p className="hint">按本机时区，生成在 05:00 预跑，07:30 推送。</p>
      </section>

      <section className="form-block">
        <span className="t-label">渠道</span>
        <div className="channel-row">
          {CHANNELS.map((channel) => (
            <label key={channel.key} className="done">
              <input
                type="checkbox"
                checked={channels.includes(channel.key)}
                onChange={(e) =>
                  setChannels((prev) =>
                    e.target.checked ? [...prev, channel.key] : prev.filter((c) => c !== channel.key),
                  )
                }
              />
              {channel.label}
            </label>
          ))}
        </div>
        <p className="hint">邮件需要在 .env 里配 SMTP。没配就只走站内。</p>
      </section>

      <div className="form-actions">
        <button
          className="ghost solid"
          type="button"
          onClick={() => save.mutate({ kind, time_of_day: time, channels, active: true })}
          disabled={save.isPending}
        >
          {save.isPending ? '保存中' : '保存订阅'}
        </button>
        <button className="ghost" type="button" onClick={() => test.mutate()} disabled={test.isPending}>
          {test.isPending ? '发送中' : '发一封测试邮件'}
        </button>
        {save.isSuccess ? <span className="hint">已保存。</span> : null}
        {test.data ? (
          <span className="hint">
            {test.data.delivered ? '发出去了。' : `没发出去：${test.data.results?.[0]?.reason ?? '未知原因'}`}
          </span>
        ) : null}
      </div>
    </div>
  );
}
