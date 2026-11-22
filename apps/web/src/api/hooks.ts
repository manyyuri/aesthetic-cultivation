import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { Issue, Item } from './client';

export function useTodayIssue() {
  return useQuery({
    queryKey: ['issue', 'today'],
    queryFn: async () => {
      const res = await fetch('/api/issues/today');
      const body = await res.json();
      return { status: res.status, body } as { status: number; body: Issue | { status: string; message: string } };
    },
  });
}

export function useIssueList(limit = 40) {
  return useQuery({
    queryKey: ['issues', limit],
    queryFn: async () => {
      const { data } = await api.GET('/api/issues', { params: { query: { limit } } });
      return (data ?? []) as Issue[];
    },
  });
}

export function useIssue(issueId?: string) {
  return useQuery({
    queryKey: ['issue', issueId],
    enabled: Boolean(issueId),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{issue_id}', {
        params: { path: { issue_id: issueId! } },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data as unknown as Issue;
    },
  });
}

export function useItem(itemId?: string) {
  return useQuery({
    queryKey: ['item', itemId],
    enabled: Boolean(itemId),
    queryFn: async () => {
      const { data } = await api.GET('/api/items/{item_id}', {
        params: { path: { item_id: itemId! } },
      });
      return data as unknown as Item;
    },
  });
}

export function useToggleDone() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { issueId: string; ord: number; done: boolean }) => {
      const { data } = await api.POST('/api/issues/{issue_id}/items/{ordinal}/done', {
        params: { path: { issue_id: args.issueId, ordinal: args.ord } },
        body: { done: args.done },
      });
      return data as { done_count: number; total: number; streak: number };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['issue'] });
    },
  });
}

export function useSubscription() {
  return useQuery({
    queryKey: ['subscription'],
    queryFn: async () => {
      const { data } = await api.GET('/api/subscriptions');
      return data as {
        id: string | null;
        kind: 'daily' | 'weekly';
        time_of_day: string;
        channels: string[];
        active: boolean;
        streak: number;
        last_done_date: string | null;
      };
    },
  });
}

export function useSaveSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      kind: 'daily' | 'weekly';
      time_of_day: string;
      channels: string[];
      active: boolean;
    }) => {
      const { data } = await api.PUT('/api/subscriptions', { body });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscription'] }),
  });
}

export function useTestPush() {
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.POST('/api/subscriptions/test');
      return data as { delivered: boolean; results: { channel: string; ok: boolean; reason?: string }[] };
    },
  });
}
