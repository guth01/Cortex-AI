// ============================================================
// Shared TypeScript types — mirrors backend Pydantic models
// ============================================================

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
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
    wikipedia_used?: boolean;
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
  easiness_factor: number;
  interval: number;
  repetitions: number;
  next_review: string;
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
  wikipedia_used?: boolean;
  wikipedia_title?: string;
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
    wikipedia_used: boolean;
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
