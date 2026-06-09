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
      // Sort: unreviewed (repetitions = 0) cards first
      const sorted = [...data].sort((a, b) => a.repetitions - b.repetitions);
      setFlashcards(sorted);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load flashcards');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => { fetch(); }, [fetch]);

  const reviewCard = async (id: string, quality: number) => {
    // Optimistic update: mark it as reviewed immediately to prevent UI jumps
    setFlashcards((prev) =>
      prev.map((card) => {
        if (card.id === id) {
          // Optimistically mark as reviewed
          return { ...card, repetitions: card.repetitions + 1 };
        }
        return card;
      })
    );
    
    try {
      await apiClient.post(`/flashcards/${id}/review`, { quality });
    } catch {
      // Revert on error
      await fetch();
    }
  };

  return { flashcards, loading, error, refetch: fetch, reviewCard };
}
