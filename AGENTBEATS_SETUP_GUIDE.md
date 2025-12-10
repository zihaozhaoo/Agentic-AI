# AgentBeats Setup Guide - NYC Ride-Hailing System

This guide shows you how to run and register both white and green agents to the AgentBeats platform.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentBeats Platform                       │
│  Backend: http://localhost:9000                             │
│  Frontend: http://localhost:5173                            │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
          ┌─────────────────┼─────────────────┐
          │                                   │
┌─────────▼──────────┐              ┌────────▼─────────┐
│   White Agent      │              │   Green Agent    │
│  (Request Parser)  │◄────────────►│  (Orchestrator)  │
│  Port: 8001        │              │  Port: 8002      │
└────────────────────┘              └──────────────────┘
```

## Prerequisites

1. **Install AgentBeats SDK** (if not already installed):
```bash
cd /Users/jiangwolin/Downloads/Agentic-AI
pip install -e .
```

2. **Set OpenAI API Key**:
```bash
export OPENAI_API_KEY="your-openai-api-key"
# Or on Windows PowerShell:
# $env:OPENAI_API_KEY="your-openai-api-key"
```

3. **Verify agentbeats CLI works**:
```bash
agentbeats --help
```

If you get "No module named 'agentbeats.cli'" error, reinstall:
```bash
pip uninstall agentbeats
pip install -e .
```

---

## Step 1: Deploy AgentBeats Platform

Start the backend and frontend servers:

```bash
agentbeats deploy --deploy_mode dev
```

**What this does:**
- Starts backend API on `http://localhost:9000`
- Starts frontend UI on `http://localhost:5173`
- Runs in development mode (no authentication required)

**Verify it's running:**
- Backend: `curl http://localhost:9000/health`
- Frontend: Open browser to `http://localhost:5173`

**Keep this terminal running!**

---

## Step 2: Start White Agent (Request Parser)

In a **new terminal**, start the white agent:

```bash
cd /Users/jiangwolin/Downloads/Agentic-AI
source .venv/bin/activate  # Or your virtual environment

python agentbeats_adapter.py
```

**What this does:**
- Loads `agent_card.toml` (Regex Baseline Agent)
- Starts A2A server on `http://localhost:8001`
- Parses natural language ride requests into structured data

**Verify it's running:**
```bash
curl http://localhost:8001/
```

**Keep this terminal running!**

---

## Step 3: Start Green Agent (Orchestrator)

In a **new terminal**, start the green agent:

```bash
cd /Users/jiangwolin/Downloads/Agentic-AI
source .venv/bin/activate  # Or your virtual environment

python green_agentbeats_adapter.py
```

**What this does:**
- Loads `green_agent_card.toml` (NYC Ride-Hailing Green Agent)
- Starts A2A server on `http://localhost:8002`
- Orchestrates battles and evaluates white agents

**Verify it's running:**
```bash
curl http://localhost:8002/
```

**Keep this terminal running!**

---

## Step 4: Register Agents to AgentBeats Platform

Now register both agents to the platform.

### Option A: Using curl (Command Line)

#### Register Green Agent:

```bash
curl -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "alias": "NYC Green Agent",
    "agent_url": "http://localhost:8002",
    "launcher_url": "http://localhost:8002",
    "role": "green"
  }'
```

**Save the `agent_id` from the response!** Example response:
```json
{
  "agent_id": "green_agent_123",
  "alias": "NYC Green Agent",
  "status": "registered"
}
```

#### Register White Agent:

```bash
curl -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "alias": "Regex Baseline Agent",
    "agent_url": "http://localhost:8001",
    "launcher_url": "http://localhost:8001",
    "role": "white"
  }'
```

**Save the `agent_id` from the response!**

### Option B: Using the Web UI

1. Open browser to `http://localhost:5173`
2. Navigate to "Agents" page
3. Click "Register New Agent"
4. Fill in the form:

**For Green Agent:**
- **Alias**: NYC Green Agent
- **Agent URL**: http://localhost:8002
- **Launcher URL**: http://localhost:8002
- **Role**: green

**For White Agent:**
- **Alias**: Regex Baseline Agent
- **Agent URL**: http://localhost:8001
- **Launcher URL**: http://localhost:8001
- **Role**: white

5. Click "Register"

---

## Step 5: Create a Battle

### Option A: Using curl

```bash
curl -X POST http://localhost:9000/battles \
  -H 'Content-Type: application/json' \
  -d '{
    "battle_name": "NYC Ride Allocation Test",
    "green_agent_id": "green_agent_123",
    "white_agent_ids": ["white_agent_456"],
    "scenario": "ride_hailing",
    "config": {
      "num_vehicles": 100,
      "num_requests": 10
    }
  }'
```

Replace `green_agent_123` and `white_agent_456` with the actual agent IDs from Step 4.

### Option B: Using the Web UI

1. Go to "Battles" page
2. Click "Create Battle"
3. Fill in:
   - **Battle Name**: NYC Ride Allocation Test
   - **Green Agent**: NYC Green Agent
   - **White Agents**: Regex Baseline Agent
   - **Scenario**: Ride Hailing
4. Click "Start Battle"

---

## Step 6: Monitor Battle Progress

### View in Web UI:
1. Go to "Battles" page
2. Click on your battle
3. Watch real-time progress

### Check Status via API:
```bash
curl http://localhost:9000/battles/{battle_id}
```

---

## Alternative: Using AgentBeats CLI (Advanced)

You can also run agents using the `agentbeats run` command:

### Start Green Agent with CLI:

```bash
agentbeats run green_agent_card.toml \
  --launcher_host localhost --launcher_port 9030 \
  --agent_host localhost --agent_port 8002 \
  --mcp http://localhost:9001/sse \
  --tool green_agent_tools.py \
  --model_type openai --model_name gpt-4o-mini
```

### Start White Agent with CLI:

```bash
agentbeats run agent_card.toml \
  --launcher_host localhost --launcher_port 9020 \
  --agent_host localhost --agent_port 8001 \
  --model_type openai --model_name gpt-4o-mini
```

---

## Troubleshooting

### Error: "No module named 'agentbeats.cli'"
**Solution**: Reinstall from correct directory:
```bash
cd /Users/jiangwolin/Downloads/Agentic-AI
pip uninstall agentbeats
pip install -e .
```

### Error: "Address already in use"
**Solution**: Kill existing process on that port:
```bash
lsof -ti:8001 | xargs kill -9  # For white agent
lsof -ti:8002 | xargs kill -9  # For green agent
```

### Error: "Connection refused"
**Solution**: Ensure AgentBeats platform is running:
```bash
curl http://localhost:9000/health
```

### Error: "File not found: taxi_zone_lookup.csv"
**Solution**: Ensure you have the required data files:
- `taxi_zone_lookup.csv`
- `fhvhv_tripdata_2025-01.parquet`

Download from NYC TLC if missing: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

---

## Testing the Green Agent Directly

You can test the green agent without the full platform:

```bash
# Initialize a battle
curl -X POST http://localhost:8002/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "parts": [{
      "type": "text",
      "content": "{\"command\": \"initialize_battle\", \"num_vehicles\": 50, \"num_requests\": 5}"
    }]
  }'

# Get status
curl -X POST http://localhost:8002/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "parts": [{
      "type": "text",
      "content": "{\"command\": \"get_status\"}"
    }]
  }'
```

---

## Quick Reference

| Component | URL | Description |
|-----------|-----|-------------|
| AgentBeats Backend | http://localhost:9000 | Platform API |
| AgentBeats Frontend | http://localhost:5173 | Web UI |
| White Agent | http://localhost:8001 | Request parser |
| Green Agent | http://localhost:8002 | Orchestrator |

## Next Steps

1. ✅ All agents running
2. ✅ Agents registered to platform
3. ✅ Battle created
4. 🎯 Implement your own white agent
5. 🎯 Compete on the leaderboard!
