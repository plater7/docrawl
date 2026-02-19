#!/bin/bash
# Docrawl Setup Script
# Ensures all prerequisites are met before running Docrawl
#
# 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Docrawl Setup Script${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

ERRORS=0
WARNINGS=0

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is NOT installed"
        return 1
    fi
}

check_docker_running() {
    if docker info &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker daemon is running"
        return 0
    else
        echo -e "${RED}✗${NC} Docker daemon is NOT running"
        return 1
    fi
}

get_total_memory_gb() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo $(($(sysctl -n hw.memsize) / 1073741824))
    else
        local mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        echo $((mem_kb / 1048576))
    fi
}

# Check Docker
echo -e "${BLUE}Checking Docker...${NC}"
if ! check_command docker; then
    ERRORS=$((ERRORS + 1))
    echo -e "  ${YELLOW}→ Install Docker: https://docs.docker.com/get-docker/${NC}"
else
    if ! check_docker_running; then
        ERRORS=$((ERRORS + 1))
        echo -e "  ${YELLOW}→ Start Docker Desktop or run: sudo systemctl start docker${NC}"
    fi
fi

# Check Docker Compose
echo ""
echo -e "${BLUE}Checking Docker Compose...${NC}"
if docker compose version &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker Compose is available (plugin)"
elif check_command docker-compose; then
    echo -e "${GREEN}✓${NC} docker-compose is installed (standalone)"
else
    ERRORS=$((ERRORS + 1))
    echo -e "${RED}✗${NC} Docker Compose is NOT installed"
    echo -e "  ${YELLOW}→ Install: https://docs.docker.com/compose/install/${NC}"
fi

# Check memory
echo ""
echo -e "${BLUE}Checking system resources...${NC}"
TOTAL_MEM=$(get_total_memory_gb)
MIN_MEM=4
if [[ $TOTAL_MEM -ge $MIN_MEM ]]; then
    echo -e "${GREEN}✓${NC} Memory: ${TOTAL_MEM}GB (minimum: ${MIN_MEM}GB)"
else
    echo -e "${YELLOW}!${NC} Memory: ${TOTAL_MEM}GB (recommended: ${MIN_MEM}GB+)"
    echo -e "  ${YELLOW}→ Docrawl may run slowly. Consider adding more RAM.${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check disk space
DATA_DIR="./data"
if [[ -d "$DATA_DIR" ]]; then
    AVAILABLE=$(df -BG "$DATA_DIR" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
else
    AVAILABLE=$(df -BG . 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
fi
MIN_DISK=5
if [[ -n "$AVAILABLE" && "$AVAILABLE" -ge $MIN_DISK ]]; then
    echo -e "${GREEN}✓${NC} Disk space: ${AVAILABLE}GB available (minimum: ${MIN_DISK}GB)"
else
    echo -e "${YELLOW}!${NC} Disk space: ${AVAILABLE}GB available (recommended: ${MIN_DISK}GB+)"
    echo -e "  ${YELLOW}→ Crawls can generate large files. Free up disk space.${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Create data directory
echo ""
echo -e "${BLUE}Setting up directories...${NC}"
mkdir -p ./data
chmod 755 ./data
echo -e "${GREEN}✓${NC} Created ./data directory"

# Create .env from example if not exists
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo -e "${GREEN}✓${NC} Created .env from .env.example"
        echo -e "  ${YELLOW}→ Edit .env to add your API keys if using OpenRouter/OpenCode${NC}"
    else
        echo -e "${YELLOW}!${NC} .env.example not found, skipping .env creation${NC}"
    fi
else
    echo -e "${GREEN}✓${NC} .env already exists"
fi

# Check Ollama (optional but recommended)
echo ""
echo -e "${BLUE}Checking Ollama (optional)...${NC}"
if check_command ollama; then
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        MODEL_COUNT=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "0")
        if [[ "$MODEL_COUNT" -gt 0 ]]; then
            echo -e "${GREEN}✓${NC} Ollama is running with $MODEL_COUNT model(s)"
        else
            echo -e "${YELLOW}!${NC} Ollama is running but has no models"
            echo -e "  ${YELLOW}→ Pull a model: ollama pull mistral:7b${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo -e "${YELLOW}!${NC} Ollama installed but not running"
        echo -e "  ${YELLOW}→ Start with: ollama serve${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${YELLOW}!${NC} Ollama is not installed"
    echo -e "  ${YELLOW}→ Install from: https://ollama.ai${NC}"
    echo -e "  ${YELLOW}→ Or use OpenRouter/OpenCode API instead (set API keys in .env)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Playwright download warning
echo ""
echo -e "${BLUE}Important Notes:${NC}"
echo -e "  ${YELLOW}→${NC} First build will download Playwright Chromium (~200MB)"
echo -e "  ${YELLOW}→${NC} Ensure you have internet connectivity for the build"
echo -e "  ${YELLOW}→${NC} If using Ollama, pull models before crawling:"
echo -e "     ollama pull mistral:7b       # Crawl model (fast)"
echo -e "     ollama pull qwen2.5:14b      # Pipeline model (balanced)"
echo -e "     ollama pull deepseek-r1:7b   # Reasoning model (optional)"

# Summary
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}Errors: $ERRORS${NC} - Must fix before running Docrawl"
    echo ""
    echo "Run the following to fix issues and try again:"
    echo "  ./setup.sh"
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo -e "${YELLOW}Warnings: $WARNINGS${NC} - Docrawl may not work optimally"
    echo ""
    echo "You can proceed, but consider addressing the warnings above."
    echo ""
    echo -e "${GREEN}Ready to start:${NC}"
    echo "  docker compose up --build"
else
    echo -e "${GREEN}All checks passed!${NC}"
    echo ""
    echo "Ready to start:"
    echo "  docker compose up --build"
    echo ""
    echo "Then open: http://localhost:8002"
fi
