'use client';
import { useState, useEffect, useCallback } from 'react';
import apiClient from '@/lib/apiClient';
import type { Session } from '@/types';

export function useSessions(subjectId?: string) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = subjectId ? { subject_id: subjectId } : {};
      const { data } = await apiClient.get<Session[]>('/sessions', { params });
      setSessions(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => { fetch(); }, [fetch]);

  const startSession = async (subjectId: string, documentIds: string[], topics: string[]) => {
    // Session start can take 60-120s for large documents (parse + chunk + embed).
    // Override the default 30s timeout to 5 minutes for this call only.
    const { data } = await apiClient.post<{ session_id: string; docs_loaded: number; chunk_count: number }>(
      '/sessions/start',
      { subject_id: subjectId, document_ids: documentIds, topics },
      { timeout: 300_000 }
    );
    return data;
  };

  const endSession = async (sessionId: string) => {
    const { data } = await apiClient.post(`/sessions/${sessionId}/end`);
    return data;
  };

  const getSession = async (sessionId: string): Promise<Session> => {
    const { data } = await apiClient.get<Session>(`/sessions/${sessionId}`);
    return data;
  };

  return { sessions, loading, error, refetch: fetch, startSession, endSession, getSession };
}
