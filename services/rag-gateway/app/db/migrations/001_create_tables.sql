-- Migration 001: Create RAG Gateway tables
-- Description: Initial schema for documents, chunks, sync_jobs, and search_history
-- Author: Claude Opus 4.5
-- Date: 2026-01-14

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Table: documents
-- Stores metadata for ingested documents from IRIS cases
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    document_name VARCHAR(512) NOT NULL,
    document_type VARCHAR(50),
    file_size BIGINT,
    file_hash VARCHAR(64),
    storage_path TEXT,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    doc_metadata JSONB
);

-- Indexes for documents table
CREATE INDEX IF NOT EXISTS idx_documents_case_id ON documents(case_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);

-- Table: chunks
-- Text chunks with embeddings for semantic search
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    case_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    token_count INTEGER,
    chunk_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for chunks table
CREATE INDEX IF NOT EXISTS idx_chunks_case_id ON chunks(case_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

-- Vector index for similarity search using IVFFlat
-- Note: For datasets > 100k vectors, consider HNSW index for better performance
-- CREATE INDEX idx_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Table: sync_jobs
-- Track sync operations from IRIS to RAG database
CREATE TABLE IF NOT EXISTS sync_jobs (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    documents_synced INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    job_metadata JSONB
);

-- Indexes for sync_jobs table
CREATE INDEX IF NOT EXISTS idx_sync_jobs_case_id ON sync_jobs(case_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status);

-- Table: search_history
-- Audit log of search queries for analytics
CREATE TABLE IF NOT EXISTS search_history (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    case_id INTEGER,
    results_count INTEGER,
    executed_at TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(255),
    response_time_ms INTEGER
);

-- Indexes for search_history table
CREATE INDEX IF NOT EXISTS idx_search_history_executed_at ON search_history(executed_at DESC);

-- Comments for documentation
COMMENT ON TABLE documents IS 'Metadata for ingested documents from IRIS cases';
COMMENT ON TABLE chunks IS 'Text chunks with embeddings for semantic search';
COMMENT ON TABLE sync_jobs IS 'Track sync operations from IRIS to RAG database';
COMMENT ON TABLE search_history IS 'Audit log of search queries for analytics';

COMMENT ON COLUMN documents.file_hash IS 'SHA-256 hash for deduplication';
COMMENT ON COLUMN chunks.embedding IS '384-dimensional Sentence Transformer embedding';
COMMENT ON COLUMN chunks.case_id IS 'Denormalized for fast filtering';
COMMENT ON COLUMN sync_jobs.status IS 'Values: pending, running, completed, failed';
