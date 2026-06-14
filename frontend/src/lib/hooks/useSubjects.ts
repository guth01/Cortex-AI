'use client';
import { useState, useEffect, useCallback } from 'react';
import apiClient from '@/lib/apiClient';
import type { Subject } from '@/types';

export function useSubjects() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<Subject[]>('/subjects');
      setSubjects(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load subjects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const createSubject = async (name: string, exam_date?: string) => {
    const formattedDate = exam_date ? new Date(exam_date).toISOString() : null;
    const { data } = await apiClient.post<Subject>('/subjects', { name, exam_date: formattedDate });
    setSubjects((prev) => [data, ...prev]);
    return data;
  };

  const deleteSubject = async (id: string) => {
    // Optimistic update
    const previous = [...subjects];
    setSubjects((prev) => prev.filter((s) => s.id !== id));
    setError(null);
    try {
      await apiClient.delete(`/subjects/${id}`);
    } catch (e: unknown) {
      // Rollback on failure
      setSubjects(previous);
      const msg = e instanceof Error ? e.message : 'Failed to delete subject';
      setError(msg);
      throw new Error(msg);
    }
  };

  return { subjects, loading, error, refetch: fetch, createSubject, deleteSubject };
}
