export interface GenerateRequest {
  task: string;
  temperature?: number;
  user_id?: string;
  run_test?: boolean;
  chat_id?: string | null;
  feedback?: string | null;
  use_rag?: boolean | null;
}

export interface TokenMessage {
  type: 'token';
  data: string;
}

export interface DoneMessage {
  type: 'done';
  code: string;
  valid: boolean;
  error: string | null;
  attempts: number;
  chat_id: string;
  sandbox_result: SandboxResult | null;
  rag: RagMeta;
  timing_ms: number;
}

export interface SandboxResult {
  success: boolean;
  output: string | null;
  error: string | null;
  execution_time: number;
}

export interface RagMeta {
  used: boolean;
  sources: RagSource[];
}

export interface RagSource {
  filename: string;
  score: number;
  preview: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  code?: string;
  sandbox_result?: SandboxResult | null;
  rag?: RagMeta;
  timing_ms?: number;
  timestamp: Date;
}

export type StreamMessage = TokenMessage | DoneMessage;

export interface UploadedDocument {
  id: string;
  filename: string;
  description?: string;
  chunk_count?: number;
  status?: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at?: string;
  user_id?: string;
  file_type?: string;
  file_size?: number;
}