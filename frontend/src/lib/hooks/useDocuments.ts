'use client';
import { useState, useEffect, useCallback } from 'react';
import apiClient from '@/lib/apiClient';
import type { Document } from '@/types';

export function useDocuments(subjectId?: string) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = subjectId ? { subject_id: subjectId } : {};
      const { data } = await apiClient.get<Document[]>('/documents', { params });
      setDocuments(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => { fetch(); }, [fetch]);

  const uploadDocument = async (file: File, subjectId?: string) => {
    const form = new FormData();
    form.append('file', file);
    if (subjectId) form.append('subject_id', subjectId);
    const { data } = await apiClient.post<Document>('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    setDocuments((prev) => [data, ...prev]);
    return data;
  };

  const deleteDocument = async (id: string) => {
    await apiClient.delete(`/documents/${id}`);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  };

  return { documents, loading, error, refetch: fetch, uploadDocument, deleteDocument };
}
