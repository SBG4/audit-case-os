-- Enable pgvector extension in rag_db
\c rag_db;
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';

\echo 'pgvector extension enabled in rag_db'
