#!/bin/bash
# Test script to verify green and white agents are working

echo "=========================================="
echo "Testing NYC Ride-Hailing Agents"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test White Agent
echo -e "${YELLOW}Testing White Agent (port 8001)...${NC}"
WHITE_RESPONSE=$(curl -s http://localhost:8001/ 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ White Agent is running${NC}"
else
    echo -e "${RED}✗ White Agent is NOT running${NC}"
    echo "  Start it with: python agentbeats_adapter.py"
fi
echo ""

# Test Green Agent
echo -e "${YELLOW}Testing Green Agent (port 8002)...${NC}"
GREEN_RESPONSE=$(curl -s http://localhost:8002/ 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Green Agent is running${NC}"
else
    echo -e "${RED}✗ Green Agent is NOT running${NC}"
    echo "  Start it with: python green_agentbeats_adapter.py"
fi
echo ""

# Test AgentBeats Backend
echo -e "${YELLOW}Testing AgentBeats Backend (port 9000)...${NC}"
BACKEND_RESPONSE=$(curl -s http://localhost:9000/health 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AgentBeats Backend is running${NC}"
    echo "  Response: $BACKEND_RESPONSE"
else
    echo -e "${RED}✗ AgentBeats Backend is NOT running${NC}"
    echo "  Start it with: agentbeats deploy --deploy_mode dev"
fi
echo ""

# Test AgentBeats Frontend
echo -e "${YELLOW}Testing AgentBeats Frontend (port 5173)...${NC}"
FRONTEND_RESPONSE=$(curl -s http://localhost:5173/ 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AgentBeats Frontend is running${NC}"
else
    echo -e "${RED}✗ AgentBeats Frontend is NOT running${NC}"
    echo "  Should start automatically with backend"
fi
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "If all services are running, you can:"
echo "1. Register agents via: http://localhost:5173"
echo "2. Or use the API:"
echo ""
echo "   # Register Green Agent"
echo "   curl -X POST http://localhost:9000/agents \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"alias\": \"NYC Green Agent\", \"agent_url\": \"http://localhost:8002\", \"launcher_url\": \"http://localhost:8002\", \"role\": \"green\"}'"
echo ""
echo "   # Register White Agent"
echo "   curl -X POST http://localhost:9000/agents \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"alias\": \"Regex Parser\", \"agent_url\": \"http://localhost:8001\", \"launcher_url\": \"http://localhost:8001\", \"role\": \"white\"}'"
echo ""
echo "See AGENTBEATS_SETUP_GUIDE.md for detailed instructions."
echo ""
