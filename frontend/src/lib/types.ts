export type Edit = { start: number; end: number; text: string };
export type Option = { id: string; label: string; edits: Edit[] };
export type EnhanceResponse = { schema_version: 1; request_id: string; prompt_revision: number } & (
  | { type: 'autocomplete'; insert_at: number; text: string }
  | { type: 'multiple_choice'; question: string; options: Option[] }
  | { type: 'none' }
);
export type EnhanceRequest = {
  request_id: string;
  prompt: string;
  prompt_revision: number;
  cursor_position: number;
};
export type Kind = 'skill' | 'prompt' | 'graph';
export type Source = { id: string; title: string; kind: Kind; version: number };
export type Knowledge = Source & {
  summary: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  status: string;
  content?: string;
};
export type Preview = {
  preview_id: string;
  title: string;
  kind: Kind;
  summary: string;
  tags: string[];
  expires_at: string;
};
export type Page<T> = { items: T[]; next_cursor: string | null };
export type Activity = {
  id: string;
  request_id: string;
  timestamp: string;
  operation: string;
  model: string | null;
  status: string;
  status_code: number | null;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  error_code: string | null;
};
export type RequestDetail = {
  request_id: string;
  api_calls: Activity[];
  ai_calls: Activity[];
  sources: Source[];
  expires_at: string;
};
export type ModelRole = 'extraction' | 'relevance' | 'generation' | 'summary';
export type Settings = {
  models: Record<ModelRole | 'embedding', string>;
  embedding_dimensions: number;
  providers: Record<'gemini' | 'database' | 'snowflake', { configured: boolean; status: string }>;
  logging: { mode: 'metadata_only'; retention_days: 30; payloads: false };
  classifier: { status: string; labeled_outcomes: number; model_version: string | null };
};
