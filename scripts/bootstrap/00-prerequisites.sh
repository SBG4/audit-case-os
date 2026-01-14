#!/bin/bash
set -e

echo "========================================="
echo "  AuditCaseOS Prerequisites Check"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker
echo -n "Checking Docker... "
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
    echo -e "${GREEN}✓${NC} Found Docker $DOCKER_VERSION"
else
    echo -e "${RED}✗${NC} Docker not found"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
echo -n "Checking Docker Compose... "
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version | awk '{print $4}')
    echo -e "${GREEN}✓${NC} Found Docker Compose $COMPOSE_VERSION"
else
    echo -e "${RED}✗${NC} Docker Compose not found"
    echo "Please install Docker Compose V2"
    exit 1
fi

# Check disk space
echo -n "Checking disk space... "
if command -v df &> /dev/null; then
    AVAILABLE_GB=$(df -BG . | tail -1 | awk '{print $4}' | tr -d 'G')
    if [ "$AVAILABLE_GB" -lt 50 ]; then
        echo -e "${YELLOW}⚠${NC} Only ${AVAILABLE_GB}GB available (50GB recommended)"
    else
        echo -e "${GREEN}✓${NC} ${AVAILABLE_GB}GB available"
    fi
else
    echo -e "${YELLOW}⚠${NC} Could not check disk space"
fi

# Check memory
echo -n "Checking memory... "
if command -v free &> /dev/null; then
    TOTAL_GB=$(free -g | grep Mem | awk '{print $2}')
    if [ "$TOTAL_GB" -lt 8 ]; then
        echo -e "${YELLOW}⚠${NC} Only ${TOTAL_GB}GB RAM (16GB recommended)"
    else
        echo -e "${GREEN}✓${NC} ${TOTAL_GB}GB RAM"
    fi
elif command -v sysctl &> /dev/null; then
    # macOS
    TOTAL_BYTES=$(sysctl -n hw.memsize)
    TOTAL_GB=$((TOTAL_BYTES / 1024 / 1024 / 1024))
    if [ "$TOTAL_GB" -lt 8 ]; then
        echo -e "${YELLOW}⚠${NC} Only ${TOTAL_GB}GB RAM (16GB recommended)"
    else
        echo -e "${GREEN}✓${NC} ${TOTAL_GB}GB RAM"
    fi
else
    echo -e "${YELLOW}⚠${NC} Could not check memory"
fi

# Check if ports are available
echo -n "Checking required ports... "
PORTS="8000 8080 9000 9001"
PORT_CONFLICTS=()

for PORT in $PORTS; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -an 2>/dev/null | grep -q ":$PORT.*LISTEN"; then
        PORT_CONFLICTS+=($PORT)
    fi
done

if [ ${#PORT_CONFLICTS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All ports available"
else
    echo -e "${YELLOW}⚠${NC} Ports in use: ${PORT_CONFLICTS[*]}"
    echo "   These ports are required: 8000 (IRIS), 8080 (RAG Gateway), 9000-9001 (MinIO)"
fi

echo ""
echo "========================================="
echo -e " ${GREEN}✓ Prerequisites check complete${NC}"
echo "========================================="
echo ""
echo "Next step: Run ./scripts/bootstrap/01-init-env.sh"
