// ============================================================
// Shared TypeScript types — mirrors backend Pydantic models
// ============================================================

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
  google_oauth_connected: boolean;
}

export interface Subject {
  id: string;
  user_id: string;
  name: string;
  exam_date: string | null;
  created_at: string;
}

export interface Document {
  id: string;
  user_id: string;
  subject_id: string | null;
  filename: string;
  file_path: string;
  source_type: string; // pdf | docx | md | txt
  file_size: number;
  uploaded_at: string;
  page_count: number | null;
}

export interface TranscriptMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  metadata?: {
    intent?: string;
    confidence?: number;
    chunks_used?: number;
    judge_verdict?: string;
    judge_reason?: string;
    answer_source?: string;
    awaiting_confirmation?: boolean;
  };
}

export interface Session {
  id: string;
  user_id: string;
  subject_id: string;
  documents_used: string[];
  status: 'active' | 'completed' | 'interrupted';
  started_at: string;
  ended_at: string | null;
  summary: string | null;
  transcript: TranscriptMessage[];
}

export interface Flashcard {
  id: string;
  user_id: string;
  session_id: string;
  subject_id: string;
  question: string;
  answer: string;
  card_type: string;
  topic: string;
  created_at: string;
  status: 'upcoming' | 'done';
}

export interface StudyPlanEvent {
  subject: string;
  topic: string;
  date: string;
  duration_minutes: number;
  coverage_level: 'well_covered' | 'shallow' | 'missing';
}

// SSE event payloads

export interface SSEProgress {
  type: 'progress';
  node: string;
  intent?: string;
  confidence?: number;
  chunks_found?: number;
  judge_verdict?: string;
  judge_reason?: string;
  web_results_count?: number;
  gap_analysis?: { well_covered: number; shallow: number; missing: number };
  flashcards_created?: number;
  events_proposed?: number;
}

export interface SSEResponse {
  type: 'response';
  content: string;
  metadata: {
    intent: string;
    confidence: number;
    chunks_used: number;
    judge_verdict: string | null;
    judge_reason: string | null;
    answer_source: string;
    awaiting_confirmation: boolean;
  };
}

export interface SSEPlanPending {
  type: 'plan_pending';
  proposed_events: StudyPlanEvent[];
  total_sessions: number;
  confirm_url: string;
  message: string;
}

// Fired when the Sufficiency Judge returns PARTIAL or INSUFFICIENT.
// The graph is paused — user must choose a fallback strategy before
// the answer is generated.
export interface SSEFallbackPending {
  type: 'fallback_choice_pending';
  verdict: 'PARTIAL' | 'INSUFFICIENT';
  reason: string;
  message: string;
  options: { id: 'gemini' | 'tavily'; label: string }[];
  choose_url: string;
}
