CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    embedding VECTOR(1536),
    reviewed_by_human BOOLEAN DEFAULT TRUE,
    document_id TEXT,
    parent_id TEXT,
    chunk_id TEXT,
    chunk_index INTEGER,
    category TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS parent_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_index INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata JSONB;

CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS documents_source_idx
ON documents (source);

CREATE INDEX IF NOT EXISTS documents_chunk_id_idx
ON documents (chunk_id);

CREATE INDEX IF NOT EXISTS documents_category_idx
ON documents (category);

CREATE TABLE IF NOT EXISTS csc_knowledge (
    id BIGSERIAL PRIMARY KEY,
    service_name TEXT NOT NULL,
    category TEXT,
    purpose TEXT,
    eligibility TEXT,
    prerequisites TEXT,
    fee_information TEXT,
    required_documents TEXT,
    dsp_navigation TEXT,
    form_filling_steps TEXT,
    validation_rules TEXT,
    upload_requirements TEXT,
    workflow TEXT,
    status_tracking TEXT,
    approval_process TEXT,
    download_print_process TEXT,
    common_errors TEXT,
    policies_circulars TEXT,
    comparison TEXT,
    faq TEXT,
    official_url TEXT NOT NULL,
    official_helpdesk TEXT,
    official_tracking_url TEXT,
    response_modes TEXT,
    service_keywords TEXT,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS csc_knowledge_embedding_idx
ON csc_knowledge
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS csc_knowledge_embedding_hnsw_idx
ON csc_knowledge
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS csc_knowledge_service_name_idx
ON csc_knowledge (service_name);

CREATE INDEX IF NOT EXISTS csc_knowledge_category_idx
ON csc_knowledge (category);

CREATE TABLE IF NOT EXISTS human_review_queue (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL,
    confidence NUMERIC,
    query TEXT NOT NULL,
    retrieved_context TEXT,
    draft_response TEXT,
    operator_note TEXT,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS human_review_queue_status_idx
ON human_review_queue (status, created_at DESC);
