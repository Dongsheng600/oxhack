-- Dimensions are substituted by the migration runner after strict integer validation.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE embedding_profiles (
 id uuid PRIMARY KEY, provider text NOT NULL DEFAULT 'gemini', model text NOT NULL,
 dimensions integer NOT NULL CHECK (dimensions > 0), metric text NOT NULL CHECK (metric = 'cosine'),
 normalization_version text NOT NULL DEFAULT 'nfkc-casefold-v1', active boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(model, dimensions, normalization_version)
);
CREATE UNIQUE INDEX one_active_embedding_profile ON embedding_profiles(active) WHERE active;
CREATE TABLE knowledge (
 id uuid PRIMARY KEY, title text NOT NULL, kind text NOT NULL CHECK(kind IN ('skill','prompt','graph')),
 content text NOT NULL, summary text NOT NULL, content_digest text NOT NULL,
 version integer NOT NULL DEFAULT 1 CHECK(version > 0), status text NOT NULL CHECK(status='ready'),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id, version)
);
CREATE TABLE tags (
 id uuid PRIMARY KEY, name text NOT NULL, canonical_name text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE tag_embeddings (
 tag_id uuid NOT NULL REFERENCES tags(id), profile_id uuid NOT NULL REFERENCES embedding_profiles(id),
 embedding vector(__DIMENSIONS__) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tag_id, profile_id)
);
CREATE INDEX tag_embeddings_cosine ON tag_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE TABLE knowledge_tags (
 knowledge_id uuid NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE, version integer NOT NULL,
 tag_id uuid NOT NULL REFERENCES tags(id), PRIMARY KEY(knowledge_id, version, tag_id),
 FOREIGN KEY(knowledge_id,version) REFERENCES knowledge(id,version) ON DELETE CASCADE
);
CREATE INDEX knowledge_tags_tag ON knowledge_tags(tag_id);
CREATE TABLE knowledge_previews (
 id text PRIMARY KEY, title text NOT NULL, kind text NOT NULL CHECK(kind IN ('skill','prompt','graph')),
 content text NOT NULL, summary text NOT NULL, tags jsonb NOT NULL,
 input_digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL
);
CREATE INDEX knowledge_previews_expiry ON knowledge_previews(expires_at);
CREATE TABLE ingestion_results (
 idempotency_key text PRIMARY KEY, preview_id text NOT NULL, input_digest text NOT NULL,
 knowledge_id uuid NOT NULL REFERENCES knowledge(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ingestion_failures (
 id uuid PRIMARY KEY, preview_id text NOT NULL, error_code text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL DEFAULT now()+interval '30 days'
);
CREATE TABLE model_settings (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), models jsonb NOT NULL,
 revision integer NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE policy_decisions (
 revision integer PRIMARY KEY, mode text NOT NULL CHECK(mode='metadata_only'),
 retention_days integer NOT NULL CHECK(retention_days=30), payloads boolean NOT NULL CHECK(NOT payloads),
 decided_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO policy_decisions(revision,mode,retention_days,payloads) VALUES(1,'metadata_only',30,false);
CREATE TABLE activity_logs (
 id text PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('api','ai')), request_id text NOT NULL,
 timestamp timestamptz NOT NULL, operation text NOT NULL, model text,
 status text NOT NULL CHECK(status IN ('success','error')), status_code integer,
 latency_ms integer NOT NULL CHECK(latency_ms>=0), input_tokens integer, output_tokens integer,
 error_code text, expires_at timestamptz NOT NULL,
 CHECK(expires_at<=timestamp+interval '30 days')
);
CREATE INDEX activity_logs_page ON activity_logs(kind, timestamp DESC, id DESC);
CREATE INDEX activity_logs_request ON activity_logs(request_id);
CREATE INDEX activity_logs_expiry ON activity_logs(expires_at);
CREATE TABLE request_sources (
 request_id text PRIMARY KEY, prompt_revision integer NOT NULL, sources jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 CHECK(expires_at<=created_at+interval '30 days')
);
CREATE INDEX request_sources_expiry ON request_sources(expires_at);
CREATE TABLE request_features (
 request_id text PRIMARY KEY, feature_schema integer NOT NULL DEFAULT 1, features jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 CHECK(expires_at<=created_at+interval '30 days')
);
CREATE INDEX request_features_expiry ON request_features(expires_at);
CREATE TABLE outcome_events (
 id uuid PRIMARY KEY, event_id text NOT NULL UNIQUE, request_id text NOT NULL,
 event_type text NOT NULL CHECK(event_type IN ('displayed','accepted','declined','stale','failed','observed')),
 observed_result text CHECK(observed_result IN ('helpful','unhelpful','unknown')),
 timestamp timestamptz NOT NULL, expires_at timestamptz NOT NULL, input_digest text NOT NULL,
 CHECK((event_type='observed') OR observed_result IS NULL),
 CHECK(expires_at<=timestamp+interval '30 days')
);
CREATE INDEX outcome_events_expiry ON outcome_events(expires_at);
