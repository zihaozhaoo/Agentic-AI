# Green Agent Implementation Summary

## What Was Created

I've implemented a complete **Green Agent (Orchestrator/Evaluator)** for your NYC ride-hailing system that integrates with the AgentBeats platform.

---

## Files Created

### 1. `green_agent_card.toml`
**Purpose**: Agent card defining the green agent's identity, role, and capabilities

**Key Sections**:
- **Role**: Orchestrator and evaluator for ride-hailing dispatch battles
- **Capabilities**: Request generation, fleet management, evaluation, scoring
- **Skills**: 6 defined skills (host_evaluation, generate_requests, evaluate_parsing, etc.)
- **URL**: http://localhost:8002

### 2. `green_agent_tools.py`
**Purpose**: Tool functions that the green agent can call during evaluation

**Functions**:
- `initialize_evaluation_environment()` - Set up vehicles and request simulator
- `generate_ride_requests()` - Create NL requests from NYC trip data
- `evaluate_white_agent_parsing()` - Score parsing accuracy
- `evaluate_routing_decision()` - Score vehicle allocation decisions
- `calculate_performance_metrics()` - Compute comprehensive metrics

### 3. `green_agentbeats_adapter.py`
**Purpose**: Main server that exposes the green agent via A2A protocol

**Key Features**:
- Inherits from `AgentBeatsExecutor`
- Initializes `GreenAgentEnvironment` with request simulator and vehicle fleet
- Handles commands: `initialize_battle`, `register_white_agent`, `start_battle`, `submit_response`, `get_results`
- Runs on port 8002
- Uses A2A protocol for communication

### 4. `AGENTBEATS_SETUP_GUIDE.md`
**Purpose**: Comprehensive guide for running and registering agents

**Covers**:
- System architecture
- Step-by-step setup instructions
- Agent registration (via API and Web UI)
- Battle creation
- Troubleshooting
- Testing commands

### 5. `test_agents.sh`
**Purpose**: Quick test script to verify all services are running

**Tests**:
- White agent (port 8001)
- Green agent (port 8002)
- AgentBeats backend (port 9000)
- AgentBeats frontend (port 5173)

### 6. Updated `HOWTORUN.md`
**Purpose**: Quick reference for running the system

---

## Green Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              green_agentbeats_adapter.py                     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │        GreenAgentExecutor                           │    │
│  │  (Inherits from AgentBeatsExecutor)                │    │
│  │                                                      │    │
│  │  • Handles A2A protocol messages                    │    │
│  │  • Routes commands to appropriate handlers          │    │
│  │  • Manages session state                            │    │
│  └──────────────┬───────────────────────────────────────┘    │
│                 │                                            │
│                 ▼                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │      GreenAgentEnvironment                          │    │
│  │  (from src/environment/green_agent_environment.py)  │    │
│  │                                                      │    │
│  │  • RequestSimulator: Generate NL requests           │    │
│  │  • VehicleDatabase: Manage fleet state              │    │
│  │  • VehicleSimulator: Execute trips                  │    │
│  │  • Evaluator: Calculate metrics                     │    │
│  │  • EventLogger: Track all events                    │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ A2A Protocol
                         ▼
            ┌─────────────────────────┐
            │  AgentBeats Platform    │
            │  (Backend + Frontend)   │
            └─────────────────────────┘
```

---

## How It Works

### 1. Initialization
When you run `python green_agentbeats_adapter.py`:
1. Loads `green_agent_card.toml`
2. Creates `GreenAgentExecutor` instance
3. Initializes `RequestSimulator` and `GreenAgentEnvironment`
4. Starts A2A server on port 8002

### 2. Battle Flow

#### Step 1: Initialize Battle
```bash
Command: initialize_battle
- Creates vehicle fleet (default 100 vehicles)
- Generates ride requests from NYC data (default 10 requests)
- Creates battle session with unique ID
```

#### Step 2: Register White Agents
```bash
Command: register_white_agent
- Registers participating white agents
- Stores agent metadata (ID, name, URL)
```

#### Step 3: Start Battle
```bash
Command: start_battle
- Returns first request to white agents
- Provides vehicle availability info
```

#### Step 4: Process Responses
```bash
Command: submit_response
- White agents submit parsing + routing decisions
- Green agent stores and validates responses
```

#### Step 5: Get Results
```bash
Command: get_results
- Calculates final scores
- Returns metrics for all agents
```

---

## Green Agent Capabilities

### 1. Request Generation
- **Source**: NYC TLC HVFHV trip data (20M+ trips/month)
- **Format**: Natural language templates
- **Examples**:
  - "I need a ride from Times Square to JFK Airport at 3:30 PM"
  - "Wheelchair-accessible vehicle from Penn Station to Brooklyn"

### 2. Fleet Management
- **Fleet Size**: Configurable (default 100, realistic 77K)
- **Vehicle Properties**:
  - Current location (lat/lon + zone)
  - Availability status
  - Wheelchair accessibility
  - Current trip (if assigned)
- **Updates**: Real-time as trips are assigned/completed

### 3. Evaluation Metrics

#### Parsing Metrics:
- Origin zone accuracy
- Destination zone accuracy
- Time constraint accuracy
- Special requirements accuracy (wheelchair, shared ride)
- Mean location error (miles)

#### Routing Metrics:
- **Net Revenue** = Total Revenue - Idle Costs
- Total revenue (from completed rides)
- Idle/deadhead costs (repositioning vehicles)
- Deadhead ratio (empty miles / total miles)
- Average pickup time
- Revenue per mile

### 4. Battle Orchestration
- Multi-agent coordination
- Time-stepped simulation
- Event logging
- Result aggregation
- Leaderboard data export

---

## Usage Examples

### Start All Services

**Terminal 1 - Platform:**
```bash
agentbeats deploy --deploy_mode dev
```

**Terminal 2 - White Agent:**
```bash
python agentbeats_adapter.py
```

**Terminal 3 - Green Agent:**
```bash
python green_agentbeats_adapter.py
```

**Terminal 4 - Test:**
```bash
./test_agents.sh
```

### Register Agents

```bash
# Register green agent
curl -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "alias": "NYC Green Agent",
    "agent_url": "http://localhost:8002",
    "launcher_url": "http://localhost:8002",
    "role": "green"
  }'

# Register white agent
curl -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "alias": "Regex Parser",
    "agent_url": "http://localhost:8001",
    "launcher_url": "http://localhost:8001",
    "role": "white"
  }'
```

### Test Green Agent Directly

```bash
# Initialize battle
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

## Integration with Existing Code

The green agent adapter **reuses** your existing implementation:

| Existing Module | Used By Green Agent |
|----------------|---------------------|
| `src/environment/green_agent_environment.py` | ✅ Core orchestration logic |
| `src/request_simulation/` | ✅ Generate NL requests |
| `src/vehicle_system/` | ✅ Manage fleet state |
| `src/evaluation/` | ✅ Calculate metrics |
| `src/utils/` | ✅ Event logging |
| `src/white_agent/` | ✅ Data structures |

**What's New**:
- A2A protocol wrapper (`green_agentbeats_adapter.py`)
- AgentBeats platform integration
- Battle orchestration commands
- Tool definitions (`green_agent_tools.py`)

---

## Next Steps

### 1. Basic Testing
```bash
# Start all services
./test_agents.sh

# Register agents
# See AGENTBEATS_SETUP_GUIDE.md
```

### 2. Create Your First Battle
- Use Web UI (http://localhost:5173)
- Or API commands (see guide)

### 3. Implement Custom White Agent
- Inherit from `WhiteAgentBase`
- Implement `parse_request()` and `make_routing_decision()`
- Create your own `my_white_agent_card.toml`
- Run your agent and compete!

### 4. Scale Up
- Increase vehicles: `num_vehicles=77000`
- Increase requests: `num_requests=1000`
- Add Google Maps API for exact distances
- Implement advanced routing algorithms

---

## Key Differences: White vs Green Agent

| Aspect | White Agent | Green Agent |
|--------|-------------|-------------|
| **Role** | Contestant | Judge |
| **Port** | 8001 | 8002 |
| **Input** | NL ride requests | Commands to orchestrate |
| **Output** | Parsed requests + routing | Evaluation scores |
| **Example** | RegexBaselineAgent | NYC Green Agent |
| **File** | `agentbeats_adapter.py` | `green_agentbeats_adapter.py` |

---

## Troubleshooting

See `AGENTBEATS_SETUP_GUIDE.md` for detailed troubleshooting steps.

**Common Issues**:
1. `No module named 'agentbeats.cli'` → Reinstall SDK
2. `Address already in use` → Kill process on port
3. `Connection refused` → Ensure platform is running
4. `File not found` → Download NYC trip data

---

## Summary

✅ **Green agent server created** (`green_agentbeats_adapter.py`)
✅ **Agent card defined** (`green_agent_card.toml`)
✅ **Tools implemented** (`green_agent_tools.py`)
✅ **Setup guide written** (`AGENTBEATS_SETUP_GUIDE.md`)
✅ **Test script created** (`test_agents.sh`)
✅ **Integration complete** - Ready for AgentBeats platform!

You now have a fully functional green agent that can orchestrate ride-hailing dispatch battles and evaluate white agent performance on the AgentBeats platform! 🎉
