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
      setFlashcards(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load flashcards');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => { fetch(); }, [fetch]);

  const markDone = async (id: string) => {
    // Optimistic update: mark it as done immediately to prevent UI jumps
    setFlashcards((prev) =>
      prev.map((card) => {
        if (card.id === id) {
          // Optimistically mark as done
          return { ...card, status: 'done' };
        }
        return card;
      })
    );
    
    try {
      await apiClient.post(`/flashcards/${id}/mark-done`);
    } catch {
      // Revert on error
      await fetch();
    }
  };

  return { flashcards, loading, error, refetch: fetch, markDone };
}
