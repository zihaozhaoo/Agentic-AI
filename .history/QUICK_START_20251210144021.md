# NYC Ride-Hailing System - Complete Setup Guide

## 🎯 Overview

This system lets AI agents compete on ride-hailing dispatch tasks:
- **Green Agent** (Judge): Generates ride requests, evaluates performance
- **White Agent** (Player): Parses requests, makes routing decisions
- **Platform**: Manages battles, tracks scores

---

## 📋 Complete Setup Process (What We Did)

### Step 1: Deploy AgentBeats Platform

**Terminal 1:**
```bash
cd /Users/jiangwolin/Downloads/Agentic-AI
source .venv/bin/activate
agentbeats deploy --deploy_mode dev
```

**What happens:**
- ✅ Backend API starts on port 9000
- ✅ MCP server starts on port 9001
- ✅ Frontend UI starts on port 5173

**Keep running!**

---

### Step 2: Start White Agent with Launcher

**Terminal 2:**
```bash
cd /Users/jiangwolin/Downloads/Agentic-AI
source .venv/bin/activate

agentbeats run agent_card.toml \
  --launcher_host localhost --launcher_port 9020 \
  --agent_host localhost --agent_port 8001 \
  --model_type openai --model_name gpt-4o-mini
```

**Creates:**
- Launcher on port 9020 (handles battle resets)
- Agent on port 8001 (parses ride requests)

**Keep running!**

---

### Step 3: Start Green Agent with Launcher

**Terminal 3:**
```bash
cd /Users/jiangwolin/Downloads/Agentic-AI
source .venv/bin/activate

agentbeats run green_agent_card.toml \
  --launcher_host localhost --launcher_port 9030 \
  --agent_host localhost --agent_port 8002 \
  --model_type openai --model_name gpt-4o-mini
```

**Creates:**
- Launcher on port 9030 (handles resets)
- Agent on port 8002 (orchestrates battles)

**Keep running!**

---

### Step 4: Register White Agent

**Terminal 4:**
```bash
curl -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "alias": "Regex Baseline Parser",
    "agent_url": "http://localhost:8001",
    "launcher_url": "http://localhost:9020",
    "is_green": false,
    "roles": ["white"]
  }'
```

**📝 Save the `agent_id` from response!**

Example: `"agent_id": "105bc3d2-0ecb-44bd-8406-ba655513c798"`

---

### Step 5: Register Green Agent

```bash
curl -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "alias": "NYC Green Agent",
    "agent_url": "http://localhost:8002",
    "launcher_url": "http://localhost:9030",
    "is_green": true,
    "roles": ["green"],
    "participant_requirements": [
      {
        "role": "white",
        "name": "Regex Baseline Parser",
        "required": true
      }
    ]
  }'
```

**📝 Save this `agent_id` too!**

Example: `"agent_id": "015f78ee-6e9b-44e6-bd2b-65cfd28dd265"`

---

### Step 6: Create Battle

```bash
curl -X POST http://localhost:9000/battles \
  -H 'Content-Type: application/json' \
  -d '{
    "battle_name": "NYC Ride Allocation Test",
    "green_agent_id": "YOUR_GREEN_AGENT_ID",
    "opponents": [
      {
        "name": "Regex Baseline Parser",
        "agent_id": "YOUR_WHITE_AGENT_ID"
      }
    ]
  }'
```

**Replace** `YOUR_GREEN_AGENT_ID` and `YOUR_WHITE_AGENT_ID` with actual IDs!

---

### Step 7: Monitor Battle

**Check status:**
```bash
curl http://localhost:9000/battles/BATTLE_ID | python3 -m json.tool
```

**Or view in browser:**
http://localhost:5173 → Battles page

---

## 🔑 Key Concepts

### Why Separate Launcher and Agent?

| Component | Port | Purpose |
|-----------|------|---------|
| White Launcher | 9020 | Resets white agent between battles |
| White Agent | 8001 | Parses ride requests |
| Green Launcher | 9030 | Resets green agent between battles |
| Green Agent | 8002 | Orchestrates battles |

**The launcher is required** for the platform to reset agents before each battle!

### Registration Fields Explained

**`agent_url`**: Where the agent responds to requests
**`launcher_url`**: Where the launcher handles lifecycle (reset/start/stop)
**`is_green`**: true = orchestrator, false = participant
**`participant_requirements`**: What white agents the green agent needs

---

## 📊 Port Reference

| Service | Port | URL |
|---------|------|-----|
| Backend API | 9000 | http://localhost:9000 |
| MCP Server | 9001 | http://localhost:9001 |
| Frontend UI | 5173 | http://localhost:5173 |
| White Launcher | 9020 | (internal) |
| White Agent | 8001 | http://localhost:8001 |
| Green Launcher | 9030 | (internal) |
| Green Agent | 8002 | http://localhost:8002 |

---

## 🔧 Troubleshooting

**Port already in use:**
```bash
lsof -ti:9000 -ti:9001 -ti:8001 -ti:8002 | xargs kill -9
```

**Module not found:**
```bash
pip uninstall agentbeats
pip install -e .
```

**Platform not responding:**
```bash
curl http://localhost:9000/health
```

---

## 📚 More Documentation

- **Full Guide**: `AGENTBEATS_SETUP_GUIDE.md`
- **Green Agent Tech Details**: `GREEN_AGENT_SUMMARY.md`
- **Original Quick Commands**: `HOWTORUN.md`

---

## ✅ What We Accomplished

1. ✅ Platform deployed (backend + frontend + MCP)
2. ✅ White agent running with launcher
3. ✅ Green agent running with launcher
4. ✅ Both agents registered to platform
5. ✅ Battle created (currently: "Failed to notify green agent" - needs A2A message handling fix)

## 🚧 Current Status

**Battle Progress:**
- ✅ Reset works (agents reset successfully)
- ✅ Agents ready (both respond after reset)
- ❌ Battle notification (green agent needs to handle A2A messages)

**Next Step:** Fix green agent to receive battle_start messages via A2A protocol.
