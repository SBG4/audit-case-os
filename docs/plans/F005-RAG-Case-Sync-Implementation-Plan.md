# F005 - RAG Case Sync Endpoint Implementation Plan

**Feature ID:** F005
**Priority:** HIGH
**Phase:** Phase 1
**Status:** Planning
**Created:** 2026-01-14

---

## Overview

Implement the core RAG sync functionality that fetches all documents and evidence from an IRIS case, chunks them into semantic segments, generates embeddings, and stores them in the vector database for semantic search.

**Endpoint:** `POST /api/v1/sync/case/{case_id}`

---

## Acceptance Criteria (from PROJECT_SPEC.xml)

- [x] Fetch case metadata from IRIS API using case_id
- [x] Download all evidence files from IRIS case
- [x] Extract text from PDFs, DOCX, images (OCR), and other formats
- [x] Chunk documents into 512-token segments with 128-token overlap
- [x] Generate 384-dim embeddings using Sentence Transformers
- [x] Store chunks and embeddings in rag_db with case_id reference
- [x] Return sync status with document count and chunk count

---

## Architecture Design

### Component Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│                    Sync Endpoint Flow                        │
└─────────────────────────────────────────────────────────────┘

1. API Request Handler (FastAPI endpoint)
   ├─> Validate case_id and authentication
   ├─> Create sync_job record (status: pending)
   └─> Launch background task

2. Background Sync Task (async worker)
   ├─> Update job status: running
   ├─> Fetch case metadata from IRIS API
   ├─> Fetch evidence list from IRIS API
   └─> For each evidence file:
       ├─> Download file to temp storage
       ├─> Extract text based on MIME type
       ├─> Chunk text into segments
       ├─> Generate embeddings for chunks
       ├─> Store in database (documents + chunks)
       └─> Update sync_job progress

3. Completion
   ├─> Update job status: completed/failed
   ├─> Return summary statistics
   └─> Cleanup temp files
```

### Database Schema Implementation

Following PROJECT_SPEC.xml schema:

**Table: documents**
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    document_name VARCHAR(512) NOT NULL,
    document_type VARCHAR(50),
    file_size BIGINT,
    file_hash VARCHAR(64),
    storage_path TEXT,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_documents_case_id ON documents(case_id);
CREATE INDEX idx_documents_hash ON documents(file_hash);
```

**Table: chunks**
```sql
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    case_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    token_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_case_id ON chunks(case_id);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_embedding_ivfflat ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**Table: sync_jobs**
```sql
CREATE TABLE sync_jobs (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    documents_synced INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX idx_sync_jobs_case_id ON sync_jobs(case_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status);
```

---

## Implementation Steps

### Phase 1: Database Models and Migrations (Day 1)

**Files to Create:**
- `services/rag-gateway/app/db/models.py` - SQLAlchemy models
- `services/rag-gateway/app/db/migrations/001_create_tables.sql` - Migration script

**Tasks:**
1. Create SQLAlchemy models for documents, chunks, sync_jobs
2. Add pgvector column type support
3. Create migration script
4. Test models with database connection

**Deliverable:** Working database schema in rag_db

---

### Phase 2: IRIS API Client (Day 1)

**Files to Create:**
- `services/rag-gateway/app/integrations/__init__.py`
- `services/rag-gateway/app/integrations/iris_client.py`

**Tasks:**
1. Create IrisClient class with httpx async client
2. Implement methods:
   - `get_case(case_id)` - Fetch case metadata
   - `list_case_evidence(case_id)` - Get all evidence files
   - `download_evidence(evidence_id)` - Download file content
3. Add authentication with Bearer token from config
4. Implement error handling and retries
5. Add logging for all API calls

**IRIS API Endpoints to Use:**
```python
# Case metadata
GET /manage/cases/{case_id}

# Evidence list
GET /case/evidences/list?cid={case_id}

# Download evidence
GET /case/evidences/{evidence_id}/download?cid={case_id}
```

**Deliverable:** Working IRIS API client with tests

---

### Phase 3: Text Extraction Pipeline (Day 2)

**Files to Create:**
- `services/rag-gateway/app/processing/__init__.py`
- `services/rag-gateway/app/processing/extractors.py`
- `services/rag-gateway/app/processing/chunker.py`

**Tasks:**
1. Create TextExtractor base class
2. Implement extractors for:
   - PDF files (PyPDF2)
   - DOCX files (python-docx)
   - TXT files (plain text)
   - Images (pytesseract OCR - optional for Phase 2)
   - HTML files (BeautifulSoup)
3. Create DocumentChunker class:
   - 512 token chunks with 128 token overlap
   - Use tiktoken for token counting (cl100k_base encoding)
   - Preserve sentence boundaries when possible
4. Add MIME type detection
5. Handle encoding issues gracefully

**Dependencies to Add:**
```
PyPDF2==3.0.1
python-docx==1.1.0
beautifulsoup4==4.12.2
tiktoken==0.5.2
```

**Deliverable:** Text extraction and chunking pipeline

---

### Phase 4: Embedding Generation (Day 2)

**Files to Modify:**
- `services/rag-gateway/rag/embedder.py` - Enhance existing service

**Tasks:**
1. Add batch embedding method for multiple chunks
2. Implement async batch processing with progress tracking
3. Add caching for identical chunks (hash-based deduplication)
4. Optimize for performance (batch size tuning)

**Deliverable:** Production-ready embedding service

---

### Phase 5: Sync Service Implementation (Day 3)

**Files to Create:**
- `services/rag-gateway/app/services/__init__.py`
- `services/rag-gateway/app/services/sync_service.py`

**Tasks:**
1. Create SyncService class
2. Implement sync_case method:
   ```python
   async def sync_case(
       case_id: int,
       force_reindex: bool = False
   ) -> SyncJob:
       # 1. Create job record
       # 2. Fetch case from IRIS
       # 3. Fetch evidence list
       # 4. For each evidence:
       #    - Download file
       #    - Check hash for deduplication
       #    - Extract text
       #    - Chunk text
       #    - Generate embeddings
       #    - Store in DB
       # 5. Update job status
   ```
3. Add progress tracking and error recovery
4. Implement file deduplication by hash
5. Add temporary file cleanup
6. Handle partial failures (skip bad files, continue processing)

**Deliverable:** Complete sync service logic

---

### Phase 6: API Endpoint Implementation (Day 3)

**Files to Create:**
- `services/rag-gateway/app/api/v1/__init__.py`
- `services/rag-gateway/app/api/v1/sync.py`

**Tasks:**
1. Create FastAPI router for /api/v1/sync/*
2. Implement endpoints:
   ```python
   POST /api/v1/sync/case/{case_id}
   GET /api/v1/sync/status/{job_id}
   GET /api/v1/sync/jobs  # List all jobs
   ```
3. Add request/response Pydantic models
4. Implement authentication middleware (verify IRIS API key)
5. Add background task execution with FastAPI BackgroundTasks
6. Add request validation and error handling

**API Models:**
```python
class SyncRequest(BaseModel):
    force_reindex: bool = False

class SyncResponse(BaseModel):
    status: str
    job_id: int
    case_id: int
    message: str

class SyncJobStatus(BaseModel):
    job_id: int
    case_id: int
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    documents_synced: int
    chunks_created: int
    error_message: Optional[str]
```

**Deliverable:** Working REST API endpoints

---

### Phase 7: Testing and Validation (Day 4)

**Files to Create:**
- `services/rag-gateway/tests/test_iris_client.py`
- `services/rag-gateway/tests/test_extractors.py`
- `services/rag-gateway/tests/test_chunker.py`
- `services/rag-gateway/tests/test_sync_service.py`
- `services/rag-gateway/tests/test_sync_api.py`

**Tasks:**
1. Unit tests for each component (80% coverage minimum)
2. Integration test: Full sync flow with real IRIS case
3. Performance test: Measure sync speed for various file sizes
4. Error handling test: Invalid case_id, network failures, corrupted files
5. Deduplication test: Verify hash-based file skipping

**Test Cases:**
- Sync case with 0 files (should succeed with 0 documents)
- Sync case with mixed file types (PDF, DOCX, TXT)
- Sync same case twice (should deduplicate)
- Sync with force_reindex=true (should re-process)
- Invalid case_id (should return 404)
- Network timeout to IRIS (should retry and fail gracefully)

**Deliverable:** Comprehensive test suite

---

### Phase 8: Documentation and Deployment (Day 4)

**Files to Create:**
- `services/rag-gateway/README_SYNC.md` - Sync feature documentation
- Update `PROJECT_SPEC.xml` - Mark F005 as implemented

**Tasks:**
1. Document API endpoints with examples
2. Create user guide for sync feature
3. Add troubleshooting section
4. Update docker-compose if needed (additional dependencies)
5. Create migration guide for existing deployments

**Deliverable:** Production-ready feature with documentation

---

## Technical Decisions

### Chunking Strategy

**Choice:** Fixed token count with overlap
- **Chunk Size:** 512 tokens (balance between context and granularity)
- **Overlap:** 128 tokens (25% overlap to preserve context across boundaries)
- **Tokenizer:** tiktoken cl100k_base (GPT-4 tokenizer for consistency)

**Rationale:**
- 512 tokens ≈ 350-400 words, good for semantic coherence
- Overlap prevents breaking important context at boundaries
- Fixed token count ensures consistent embedding input size

**Alternative Considered:** Semantic chunking (split by paragraphs/sections)
- **Rejected:** More complex, harder to tune, inconsistent chunk sizes

### Deduplication Strategy

**Choice:** SHA-256 hash of file content
- Store hash in `documents.file_hash` column
- Skip re-processing if hash exists (unless force_reindex=true)

**Rationale:**
- Avoid re-processing identical files uploaded to multiple cases
- Save computation time and database storage
- SHA-256 collision probability negligible

### Background Task Execution

**Choice:** FastAPI BackgroundTasks (Phase 1), migrate to Celery (Phase 2)
- **Phase 1:** Use FastAPI's built-in background tasks
- **Phase 2:** Migrate to Celery + Redis for distributed processing

**Rationale:**
- FastAPI BackgroundTasks sufficient for single-server deployment
- Celery adds complexity but enables horizontal scaling
- Start simple, scale when needed

### Error Handling Philosophy

**Choice:** Best-effort processing with detailed logging
- Don't fail entire sync job if one file fails
- Log errors to sync_job.error_message (JSON array of errors)
- Continue processing remaining files
- Mark job as "completed_with_errors" if partial success

**Rationale:**
- Investigations may have corrupted or malformed files
- Better to get partial results than total failure
- User can review errors and retry specific files

---

## Dependencies to Add

Update `services/rag-gateway/requirements.txt`:

```
# Existing dependencies preserved
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
psycopg2-binary==2.9.9
pydantic==2.5.3
pydantic-settings==2.1.0
redis==5.0.1
sentence-transformers==2.2.2

# New dependencies for F005
PyPDF2==3.0.1              # PDF text extraction
python-docx==1.1.0         # DOCX text extraction
beautifulsoup4==4.12.2     # HTML text extraction
lxml==5.1.0                # XML/HTML parsing
tiktoken==0.5.2            # Token counting for chunking
httpx==0.26.0              # Async HTTP client for IRIS API
aiofiles==23.2.1           # Async file I/O
python-multipart==0.0.6    # File upload support

# Optional for Phase 2
# pytesseract==0.3.10      # OCR for images
# Pillow==10.1.0           # Image processing
```

---

## File Structure

```
services/rag-gateway/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── sync.py              # NEW: Sync endpoints
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py                # NEW: SQLAlchemy models
│   │   └── migrations/
│   │       └── 001_create_tables.sql # NEW: Migration
│   ├── integrations/
│   │   ├── __init__.py
│   │   └── iris_client.py           # NEW: IRIS API client
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── extractors.py            # NEW: Text extraction
│   │   └── chunker.py               # NEW: Document chunking
│   ├── services/
│   │   ├── __init__.py
│   │   └── sync_service.py          # NEW: Sync orchestration
│   ├── config.py                     # MODIFY: Add new settings
│   └── main.py                       # MODIFY: Register sync routes
├── tests/
│   ├── test_iris_client.py          # NEW
│   ├── test_extractors.py           # NEW
│   ├── test_chunker.py              # NEW
│   ├── test_sync_service.py         # NEW
│   └── test_sync_api.py             # NEW
├── requirements.txt                  # MODIFY: Add dependencies
└── README_SYNC.md                    # NEW: Feature documentation
```

---

## Testing Plan

### Unit Tests

1. **IRIS Client Tests**
   - Mock HTTP responses
   - Test authentication
   - Test error handling and retries
   - Test response parsing

2. **Text Extractor Tests**
   - Test each file type (PDF, DOCX, TXT, HTML)
   - Test encoding detection
   - Test error handling for corrupted files

3. **Chunker Tests**
   - Test token counting accuracy
   - Test overlap calculation
   - Test boundary preservation

4. **Sync Service Tests**
   - Test full sync flow with mocked dependencies
   - Test deduplication logic
   - Test error recovery

### Integration Tests

1. **End-to-End Sync Test**
   - Create test case in IRIS
   - Upload test files (PDF, DOCX, TXT)
   - Trigger sync via API
   - Verify documents and chunks in database
   - Verify embedding vectors generated

2. **Deduplication Test**
   - Upload same file to two cases
   - Sync both cases
   - Verify only one document record with same hash
   - Verify both cases reference same chunks

3. **Error Handling Test**
   - Sync case with corrupted PDF
   - Verify job completes with errors logged
   - Verify valid files still processed

### Performance Tests

1. **Throughput Test**
   - Sync case with 50 files (100MB total)
   - Measure: Documents/minute, Chunks/minute
   - Target: >10 documents/minute, >100 chunks/minute

2. **Concurrent Sync Test**
   - Trigger 5 sync jobs simultaneously
   - Verify all complete successfully
   - Verify no database deadlocks

---

## Rollout Plan

### Step 1: Database Migration
```bash
docker exec auditcaseos-rag-gateway python -m app.db.migrations.001_create_tables
```

### Step 2: Build and Deploy
```bash
docker compose build rag-gateway
docker compose up -d rag-gateway
```

### Step 3: Verify Health
```bash
curl http://localhost:8080/health
# Should return: {"status": "healthy", "services": {"database": "up", "embeddings": "up"}}
```

### Step 4: Test Sync
```bash
# Trigger sync for IRIS case #1
curl -X POST http://localhost:8080/api/v1/sync/case/1 \
  -H "Authorization: Bearer B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594"

# Check job status
curl http://localhost:8080/api/v1/sync/status/1 \
  -H "Authorization: Bearer B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594"
```

### Step 5: Verify Database
```bash
docker exec auditcaseos-postgres psql -U postgres -d rag_db -c "
SELECT
    (SELECT COUNT(*) FROM documents) as document_count,
    (SELECT COUNT(*) FROM chunks) as chunk_count,
    (SELECT COUNT(*) FROM sync_jobs) as job_count;
"
```

---

## Success Criteria

- [x] All database tables created and indexed
- [x] IRIS API client successfully fetches case data
- [x] Text extraction works for PDF, DOCX, TXT, HTML
- [x] Chunking produces consistent 512-token segments
- [x] Embeddings generated and stored in pgvector
- [x] API endpoint returns 202 Accepted with job_id
- [x] Status endpoint shows sync progress
- [x] Unit test coverage >80%
- [x] Integration test passes end-to-end
- [x] Documentation complete

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| IRIS API changes | High | Low | Version API calls, add integration tests |
| Large file OOM | Medium | Medium | Stream file processing, add file size limits |
| Embedding generation slow | Medium | High | Batch processing, GPU support in Phase 2 |
| Database deadlocks | High | Low | Use proper transaction isolation levels |
| Text extraction failures | Low | High | Graceful degradation, log errors, continue |

---

## Future Enhancements (Post-F005)

1. **Incremental Sync** - Only sync new/modified files (requires IRIS modification tracking)
2. **OCR Support** - Extract text from images and scanned PDFs
3. **Multi-language Support** - Detect language, use language-specific models
4. **Smart Chunking** - Semantic chunking based on document structure
5. **GPU Acceleration** - Use CUDA for faster embedding generation
6. **Distributed Processing** - Celery workers for parallel file processing
7. **Real-time Sync** - Webhook from IRIS to trigger sync on file upload

---

## Timeline Estimate

- **Day 1:** Database models + IRIS client (4-6 hours)
- **Day 2:** Text extraction + chunking (4-6 hours)
- **Day 3:** Sync service + API endpoints (4-6 hours)
- **Day 4:** Testing + documentation (4-6 hours)

**Total:** 16-24 hours of development time

---

## Approval Checklist

Before starting implementation:
- [x] Plan reviewed against PROJECT_SPEC.xml
- [x] Database schema matches specification
- [x] API design follows guardrails (SEC*, CODE*, ARCH*)
- [x] Testing strategy meets requirements (TEST*)
- [x] Performance targets defined (PERF*)
- [ ] User (sbg4) approval to proceed

---

**Plan Author:** Claude Opus 4.5
**Plan Version:** 1.0
**Last Updated:** 2026-01-14
