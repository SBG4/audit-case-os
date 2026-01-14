#!/bin/bash
set -e

echo "========================================="
echo "  AuditCaseOS Environment Setup"
echo "========================================="
echo ""

# Navigate to project root
cd "$(dirname "$0")/../.."

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -f .env ]; then
    echo -e "${YELLOW}⚠ .env file already exists${NC}"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting without changes"
        exit 0
    fi
fi

echo "Generating secure random values..."

# Generate secure random values
POSTGRES_PASSWORD=$(openssl rand -base64 32)
IRIS_SECRET_KEY=$(openssl rand -base64 48)
IRIS_SECURITY_PASSWORD_SALT=$(openssl rand -base64 32)
IRIS_DB_PASSWORD=$(openssl rand -base64 32)
MINIO_ROOT_PASSWORD=$(openssl rand -base64 32)
ONLYOFFICE_JWT_SECRET=$(openssl rand -base64 32)
PAPERLESS_SECRET_KEY=$(openssl rand -base64 48)
PAPERLESS_DB_PASSWORD=$(openssl rand -base64 32)
NEXTCLOUD_DB_PASSWORD=$(openssl rand -base64 32)

# Create .env file
cat > .env << EOF
#################################################
# AuditCaseOS Configuration
# Generated: $(date)
# IMPORTANT: Review and update passwords/keys
#################################################

# === Project Configuration ===
COMPOSE_PROJECT_NAME=auditcaseos
COMPOSE_PROFILES=core

# === Core Database ===
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# === DFIR-IRIS Configuration ===
IRIS_DB_USER=iris
IRIS_DB_PASSWORD=${IRIS_DB_PASSWORD}
IRIS_SECRET_KEY=${IRIS_SECRET_KEY}
IRIS_SECURITY_PASSWORD_SALT=${IRIS_SECURITY_PASSWORD_SALT}
IRIS_ADMIN_EMAIL=admin@auditcaseos.local
IRIS_ADMIN_PASSWORD=ChangeMe123!
# NOTE: Generate API key in IRIS UI after first login
IRIS_API_KEY=

# === MinIO (S3-Compatible Storage) ===
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}

# === RAG Gateway Configuration ===
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Ollama (Optional)
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_MODELS=mistral:7b

# App Settings
LOG_LEVEL=INFO
DEBUG=false

# === Nextcloud Configuration (Phase 2) ===
NEXTCLOUD_ADMIN_USER=admin
NEXTCLOUD_ADMIN_PASSWORD=ChangeMe123!
NEXTCLOUD_DB_USER=nextcloud
NEXTCLOUD_DB_PASSWORD=${NEXTCLOUD_DB_PASSWORD}
NEXTCLOUD_DOMAIN=nextcloud.auditcaseos.local
NEXTCLOUD_URL=http://nextcloud
NEXTCLOUD_USERNAME=admin
NEXTCLOUD_PASSWORD=ChangeMe123!

# === ONLYOFFICE Configuration (Phase 2) ===
ONLYOFFICE_JWT_SECRET=${ONLYOFFICE_JWT_SECRET}

# === Paperless-ngx Configuration (Phase 2) ===
PAPERLESS_ADMIN_USER=admin
PAPERLESS_ADMIN_PASSWORD=ChangeMe123!
PAPERLESS_DB_USER=paperless
PAPERLESS_DB_PASSWORD=${PAPERLESS_DB_PASSWORD}
PAPERLESS_SECRET_KEY=${PAPERLESS_SECRET_KEY}
PAPERLESS_DOMAIN=paperless.auditcaseos.local
PAPERLESS_TOKEN=

# === Network Configuration ===
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
IRIS_DOMAIN=iris.auditcaseos.local
RAG_DOMAIN=rag.auditcaseos.local
EOF

echo -e "${GREEN}✓${NC} .env file created with secure random values"
echo ""
echo "========================================="
echo "  IMPORTANT NEXT STEPS"
echo "========================================="
echo ""
echo "1. Review .env and update these values:"
echo "   - IRIS_ADMIN_PASSWORD (default: ChangeMe123!)"
echo "   - NEXTCLOUD_ADMIN_PASSWORD (default: ChangeMe123!)"
echo "   - PAPERLESS_ADMIN_PASSWORD (default: ChangeMe123!)"
echo "   - IRIS_ADMIN_EMAIL (default: admin@auditcaseos.local)"
echo ""
echo "2. After starting IRIS, generate API key:"
echo "   - Login to IRIS UI"
echo "   - Go to: User Menu → My Settings → API Key"
echo "   - Copy the key and add to .env: IRIS_API_KEY=<key>"
echo ""
echo "3. Run: ./scripts/bootstrap/03-start-core.sh"
echo ""
