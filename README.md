# AuditCaseOS

**AI-Powered Investigation Case Management & Evidence Analysis Platform**

AuditCaseOS combines DFIR-IRIS case management with intelligent document search, RAG-based assistance, and automated reporting to streamline digital forensics and investigation workflows.

---

## Features

### Core Capabilities
- **Case Management**: DFIR-IRIS for investigation workflows, timeline, IOCs, and asset tracking
- **Evidence Storage**: MinIO (Phase 1) / Nextcloud + ONLYOFFICE (Phase 2) for collaborative document management
- **Intelligent Search**: Vector similarity search across all case evidence and knowledge base
- **AI Assistance**: RAG-powered context building and optional local SLM (Ollama) for summaries, risk assessment, and next steps
- **OCR & Indexing**: Paperless-ngx integration for automatic document processing (Phase 2)
- **Report Generation**: Automated DOCX report creation with AI-generated insights

### Technology Stack
- **Case Management**: [DFIR-IRIS](https://github.com/dfir-iris/iris-web)
- **RAG Gateway**: FastAPI + PostgreSQL + pgvector
- **Document Storage**: MinIO / Nextcloud + ONLYOFFICE
- **OCR**: Paperless-ngx + Apache Tika + Gotenberg
- **AI**: Sentence Transformers (embeddings) + Ollama (local SLM)
- **Infrastructure**: Docker Compose

---

## Quick Start

### Prerequisites
- Docker 24.0+ and Docker Compose V2
- 16GB RAM (minimum 8GB)
- 50GB free disk space
- (Optional) NVIDIA GPU for Ollama

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/audit-case-os.git
   cd audit-case-os
   ```

2. **Initialize environment**:
   ```bash
   # Run prerequisites check
   ./scripts/bootstrap/00-prerequisites.sh

   # Generate .env with secure defaults
   ./scripts/bootstrap/01-init-env.sh

   # Review and customize .env
   nano .env
   ```

3. **Start Phase 1 (MVP)**:
   ```bash
   # Start core services
   ./scripts/bootstrap/03-start-core.sh

   # Seed IRIS and initialize database
   ./scripts/bootstrap/04-seed-iris.sh
   ./scripts/bootstrap/05-seed-pgvector.sh

   # Health check
   ./scripts/bootstrap/06-health-check.sh
   ```

4. **Access Services**:
   - DFIR-IRIS: http://localhost:8000
   - RAG Gateway API: http://localhost:8080 (API docs at /docs)
   - MinIO Console: http://localhost:9001

### Phase 2 Setup (Optional)

Enable additional profiles for full capabilities:

```bash
# Update .env
COMPOSE_PROFILES=core,docs,paperless,ai

# Start additional services
docker compose up -d
```

- **Nextcloud**: http://localhost:8081
- **ONLYOFFICE**: http://localhost:8082
- **Paperless-ngx**: http://localhost:8083

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                          │
│  IRIS Web UI  │  RAG Gateway API  │  Nextcloud Web UI       │
└──────┬──────────────┬─────────────────┬─────────────────────┘
       │              │                 │
┌──────▼──────┐ ┌────▼──────────┐ ┌────▼──────────────┐
│  DFIR-IRIS  │ │  RAG-Gateway  │ │  Nextcloud        │
│  (Cases,    │ │  (FastAPI)    │ │  + ONLYOFFICE     │
│  Timeline,  │ │               │ │                   │
│  IOCs)      │ │               │ │                   │
└──────┬──────┘ └────┬──────────┘ └────┬──────────────┘
       │             │                  │
       │      ┌──────▼───────┐          │
       │      │  Paperless-  │◄─────────┘
       │      │  ngx (OCR)   │
       │      └──────┬───────┘
       │             │
       ▼             ▼
┌──────────────────────────────────────┐
│  PostgreSQL + pgvector               │
│  ├─ IRIS DB (cases, assets)          │
│  └─ RAG DB (embeddings, chunks)      │
└──────────────────────────────────────┘
```

### Data Flow

1. **Case Creation**: User creates investigation case in IRIS UI
2. **Evidence Folder**: RAG Gateway auto-creates folder in Nextcloud
3. **Document Upload**: Investigator uploads evidence files to Nextcloud
4. **OCR Processing**: Paperless-ngx extracts text from documents
5. **Embedding**: RAG Gateway chunks text and generates vector embeddings
6. **Vector Storage**: Embeddings stored in PostgreSQL with pgvector
7. **Search & Assist**: Users query via RAG Gateway API for AI-assisted insights
8. **Reporting**: Generate automated DOCX reports with evidence summary

---

## RAG Gateway API

### Core Endpoints

#### Sync Case Evidence
```bash
POST /api/v1/sync/case/{case_id}
```
Triggers full sync of case evidence from Nextcloud → Paperless → RAG index.

**Request Body**:
```json
{
  "force_refresh": false,
  "document_types": ["pdf", "docx", "email"]
}
```

#### Search
```bash
POST /api/v1/search
```
Vector similarity search across all indexed content.

**Request Body**:
```json
{
  "query": "lateral movement indicators",
  "case_id": "CASE-001",
  "top_k": 10,
  "rerank": true
}
```

**Response**:
```json
{
  "query": "lateral movement indicators",
  "total_hits": 5,
  "hits": [
    {
      "source_type": "document_chunk",
      "content": "Evidence of PowerShell remoting...",
      "score": 0.89,
      "metadata": {"case_id": "CASE-001", "filename": "network_logs.txt"}
    }
  ]
}
```

#### AI Assistance
```bash
POST /api/v1/assist/case/{case_id}
```
Build context pack and generate AI insights.

**Request Body**:
```json
{
  "include_summary": true,
  "include_risks": true,
  "include_next_steps": true
}
```

**Response**:
```json
{
  "case_id": "CASE-001",
  "summary": {
    "executive_summary": "Investigation revealed...",
    "key_findings": ["Finding 1", "Finding 2"]
  },
  "risks": [
    {
      "category": "Data Exfiltration",
      "severity": "high",
      "description": "Large data transfer detected..."
    }
  ],
  "next_steps": [
    {
      "action": "Review firewall logs for exfil confirmation",
      "priority": 1,
      "rationale": "..."
    }
  ]
}
```

#### Report Generation
```bash
GET /api/v1/report/case/{case_id}.docx
```
Generate investigation report as DOCX file.

**Query Parameters**:
- `template`: `investigation` | `executive` | `technical`
- `include_timeline`: `true` | `false`
- `include_iocs`: `true` | `false`

---

## Configuration

### Environment Variables

See [.env.example](.env.example) for all configuration options.

**Critical Settings**:
- `IRIS_API_KEY`: Generate in IRIS UI after first login (My Settings → API Key)
- `POSTGRES_PASSWORD`: Strong password for PostgreSQL
- `IRIS_SECRET_KEY`: Long random string for session encryption
- `OLLAMA_ENABLED`: Set to `true` to enable local SLM assistance

### Docker Compose Profiles

Control which services run by setting `COMPOSE_PROFILES` in `.env`:

- `core`: Essential services (IRIS, RAG Gateway, Postgres, Redis, MinIO)
- `ai`: Ollama for local SLM
- `docs`: Nextcloud + ONLYOFFICE for collaborative document editing
- `paperless`: Paperless-ngx for OCR and document processing
- `ingress`: Nginx reverse proxy

**Examples**:
```bash
# Minimal setup (Phase 1)
COMPOSE_PROFILES=core

# Full stack (Phase 2)
COMPOSE_PROFILES=core,docs,paperless,ai

# With reverse proxy
COMPOSE_PROFILES=core,docs,paperless,ingress
```

---

## Development

### Running RAG Gateway Locally

```bash
cd services/rag-gateway

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8080
```

### Running Tests

```bash
cd services/rag-gateway

# Unit tests
pytest tests/unit

# Integration tests (requires services running)
pytest tests/integration

# End-to-end tests
pytest tests/e2e
```

---

## Production Deployment

### Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Generate strong random values for `*_SECRET_KEY` variables
- [ ] Set up SSL certificates (Let's Encrypt or corporate CA)
- [ ] Enable `ingress` profile and configure nginx
- [ ] Implement backup strategy (see `scripts/backup/`)
- [ ] Configure firewall rules to restrict access
- [ ] Rotate IRIS API keys regularly
- [ ] Review CORS settings in RAG Gateway
- [ ] Enable audit logging

### Backup & Restore

```bash
# Backup all data
./scripts/backup/backup-all.sh

# Restore from backup
./scripts/backup/restore-all.sh /path/to/backup
```

---

## Troubleshooting

### IRIS Login Issues
**Problem**: Can't login to IRIS after first start

**Solution**: Check logs for default admin password
```bash
docker compose logs iris-app | grep -i password
```

### RAG Gateway Connection Errors
**Problem**: `IRIS_API_KEY` not set

**Solution**:
1. Login to IRIS UI
2. Go to: User Menu → My Settings → API Key
3. Generate new API key
4. Add to `.env`:
   ```bash
   IRIS_API_KEY=your-generated-key-here
   ```
5. Restart RAG Gateway:
   ```bash
   docker compose restart rag-gateway
   ```

### Paperless OCR Not Working
**Problem**: Documents not processing

**Solution**: Check Tika and Gotenberg are running
```bash
docker compose ps tika gotenberg
docker compose logs tika
```

### pgvector Extension Not Loaded
**Problem**: `ERROR:  extension "vector" does not exist`

**Solution**: Recreate database
```bash
docker compose down -v
docker compose up -d postgres
# Wait for postgres to start, then run init script
docker compose exec postgres psql -U postgres -d rag_db -c "CREATE EXTENSION vector;"
```

---

## Roadmap

### Phase 1: MVP (Current)
- [x] DFIR-IRIS integration
- [x] RAG Gateway with pgvector
- [x] MinIO evidence storage
- [x] Vector search and AI assistance
- [x] Basic report generation

### Phase 2: Enhanced
- [ ] Nextcloud + ONLYOFFICE integration
- [ ] Paperless-ngx OCR pipeline
- [ ] Automated evidence sync workflow
- [ ] Advanced reranking algorithms
- [ ] Custom report templates

### Phase 3: Advanced
- [ ] Real-time webhooks (IRIS → RAG)
- [ ] Multi-tenancy support
- [ ] Elasticsearch integration for hybrid search
- [ ] Custom IRIS module for embedded RAG UI
- [ ] Advanced analytics dashboard
- [ ] SOAR integration (TheHive, Cortex)

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [DFIR-IRIS](https://github.com/dfir-iris/iris-web) - Excellent DFIR case management platform
- [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) - Document management and OCR
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search in PostgreSQL
- [Sentence Transformers](https://www.sbert.net/) - State-of-the-art text embeddings
- [Ollama](https://ollama.ai/) - Local LLM inference

---

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/audit-case-os/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/audit-case-os/discussions)

---

**Built with Claude Code** | Generated with [Claude Opus 4.5](https://claude.com/claude-code)
