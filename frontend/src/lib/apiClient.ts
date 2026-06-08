import axios from 'axios';
import Cookies from 'js-cookie';

const TOKEN_KEY = 'study_agent_token';

// ─── Axios instance ──────────────────────────────────────────────────────────
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

// ─── Request interceptor: attach JWT ─────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = Cookies.get(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Response interceptor: redirect on 401 ───────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      Cookies.remove(TOKEN_KEY);
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ─── Auth helpers ─────────────────────────────────────────────────────────────
export const setToken = (token: string) => {
  Cookies.set(TOKEN_KEY, token, { expires: 7, sameSite: 'strict' });
};

export const getToken = (): string | undefined => Cookies.get(TOKEN_KEY);

export const removeToken = () => Cookies.remove(TOKEN_KEY);

export const isAuthenticated = (): boolean => !!Cookies.get(TOKEN_KEY);

// ─── SSE streaming helper ─────────────────────────────────────────────────────
/**
 * Posts to a chat endpoint and reads the SSE stream.
 * onEvent is called for each parsed event.
 */
export async function streamChat(
  sessionId: string,
  message: string,
  onEvent: (event: string, data: unknown) => void,
  signal?: AbortSignal
) {
  const token = getToken();
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/chat/${sessionId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message }),
      signal,
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE format: "event: <name>\ndata: <json>\n\n"
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      const lines = part.split('\n');
      let eventName = 'message';
      let dataStr = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) eventName = line.slice(7).trim();
        if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
      }
      if (dataStr) {
        try {
          onEvent(eventName, JSON.parse(dataStr));
        } catch {
          // ignore malformed
        }
      }
    }
  }
}

/**
 * SSE stream for confirm-plan endpoint.
 */
export async function streamConfirmPlan(
  sessionId: string,
  action: 'confirm' | 'reject',
  onEvent: (event: string, data: unknown) => void
) {
  const token = getToken();
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/chat/${sessionId}/confirm-plan`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ action }),
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  if (action === 'reject') {
    const data = await res.json();
    onEvent('response', data);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      const lines = part.split('\n');
      let eventName = 'message';
      let dataStr = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) eventName = line.slice(7).trim();
        if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
      }
      if (dataStr) {
        try {
          onEvent(eventName, JSON.parse(dataStr));
        } catch {
          // ignore
        }
      }
    }
  }
}

export default apiClient;
