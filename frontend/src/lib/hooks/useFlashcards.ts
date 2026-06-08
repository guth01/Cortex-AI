'use client';
import { useState, useEffect, useCallback } from 'react';
import apiClient from '@/lib/apiClient';
import type { Flashcard } from '@/types';

export function useFlashcards(subjectId?: string) {
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = subjectId ? { subject_id: subjectId } : {};
      const { data } = await apiClient.get<Flashcard[]>('/flashcards', { params });
      // Sort: due cards first
      const today = new Date();
      const sorted = [...data].sort((a, b) => {
        const aDue = new Date(a.next_review) <= today ? -1 : 1;
        const bDue = new Date(b.next_review) <= today ? -1 : 1;
        return aDue - bDue;
      });
      setFlashcards(sorted);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load flashcards');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => { fetch(); }, [fetch]);

  const reviewCard = async (id: string, quality: number) => {
    await apiClient.post(`/flashcards/${id}/review`, { quality });
    await fetch(); // re-fetch to get updated due dates
  };

  return { flashcards, loading, error, refetch: fetch, reviewCard };
}
