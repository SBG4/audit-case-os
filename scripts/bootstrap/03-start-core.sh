#!/bin/bash
set -e

echo "========================================="
echo "  AuditCaseOS - Starting Core Services"
echo "========================================="
echo ""

# Navigate to project root
cd "$(dirname "$0")/../.."

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}✗${NC} .env file not found"
    echo "Run: ./scripts/bootstrap/01-init-env.sh"
    exit 1
fi

# Load environment
source .env

echo "Creating data directories..."
mkdir -p data/{postgres,iris,minio,redis}

echo ""
echo "Step 1: Starting core infrastructure (Postgres, Redis, MinIO)..."
docker compose --profile core up -d postgres redis minio

echo ""
echo "Waiting for PostgreSQL to be ready..."
RETRIES=30
COUNT=0
until docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ $COUNT -gt $RETRIES ]; then
        echo -e "${RED}✗${NC} PostgreSQL failed to start after ${RETRIES} attempts"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo -e "\n${GREEN}✓${NC} PostgreSQL is ready"

echo ""
echo "Step 2: Starting DFIR-IRIS..."
docker compose --profile core up -d iris-db iris-app iris-worker

echo ""
echo "Waiting for IRIS to be ready (this may take 1-2 minutes)..."
RETRIES=60
COUNT=0
until curl -sf http://localhost:8000 > /dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ $COUNT -gt $RETRIES ]; then
        echo -e "${RED}✗${NC} IRIS failed to start after ${RETRIES} attempts"
        echo "Check logs: docker compose logs iris-app"
        exit 1
    fi
    echo -n "."
    sleep 3
done
echo -e "\n${GREEN}✓${NC} IRIS is ready"

echo ""
echo "Step 3: Starting RAG Gateway..."
docker compose --profile core up -d rag-gateway

echo ""
echo "Waiting for RAG Gateway to be ready..."
RETRIES=30
COUNT=0
until curl -sf http://localhost:8080/health > /dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ $COUNT -gt $RETRIES ]; then
        echo -e "${YELLOW}⚠${NC} RAG Gateway may not be fully ready"
        echo "Check logs: docker compose logs rag-gateway"
        break
    fi
    echo -n "."
    sleep 2
done

if [ $COUNT -le $RETRIES ]; then
    echo -e "\n${GREEN}✓${NC} RAG Gateway is ready"
fi

echo ""
echo "========================================="
echo -e " ${GREEN}✓ Core services started successfully${NC}"
echo "========================================="
echo ""
echo "Access points:"
echo "  • DFIR-IRIS:      http://localhost:8000"
echo "  • RAG Gateway:    http://localhost:8080"
echo "  • RAG API Docs:   http://localhost:8080/docs"
echo "  • MinIO Console:  http://localhost:9001"
echo ""
echo "IRIS default credentials:"
echo "  Username: administrator"
echo "  Password: (check logs for auto-generated password)"
echo ""
echo "To get the IRIS admin password, run:"
echo "  docker compose logs iris-app | grep -i 'password'"
echo ""
echo "========================================="
echo "  Next Steps"
echo "========================================="
echo ""
echo "1. Login to IRIS at http://localhost:8000"
echo "2. Generate API key:"
echo "   - Click your user menu (top right)"
echo "   - Go to 'My Settings'"
echo "   - Navigate to 'API Key' tab"
echo "   - Click 'Generate API Key'"
echo "   - Copy the key"
echo ""
echo "3. Add API key to .env:"
echo "   - Open .env file"
echo "   - Set: IRIS_API_KEY=<your-key>"
echo "   - Save file"
echo ""
echo "4. Restart RAG Gateway:"
echo "   docker compose restart rag-gateway"
echo ""
echo "5. Verify integration:"
echo "   curl http://localhost:8080/health"
echo ""
