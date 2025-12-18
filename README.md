# Agentic AI: Green Agent Framework

A comprehensive framework for evaluating AI agents on urban ride-hailing dispatch tasks.

## 🚀 Overview

This project provides a complete environment to simulate, develop, and evaluate "White Agents" (dispatch algorithms) that manage ride-hailing fleets. It includes:

- **Request Simulation**: Generates realistic natural language ride requests from NYC taxi data.
- **Vehicle System**: Simulates fleet movement, availability, and state.
- **Evaluation Engine**: Scores agents on parsing accuracy, revenue generation, and routing efficiency.
- **Green Agent Environment**: Orchestrates the interaction between the fleet, the requests, and your agent.

## ⚡️ Quick Start (Local Simulation)

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Credentials**:
   Create a `.env` file in the root directory to store your API keys (e.g., for OpenAI or Google Maps):

   ```env
   OPENAI_API_KEY=sk-...
   GOOGLE_MAPS_API_KEY=...
   ```

3. **Run the demo evaluation**:

   ```bash
   python examples/demo_evaluation.py
   ```

4. **Check the results** in the `results/` directory.

## 📊 Benchmark & Evaluation

### 1. Reproduce Benchmark Results (Comparisons)

To run the standard baselines (Random, Regex, Nearest Vehicle) and reproducing the project's benchmarks:

```bash
# Runs a large scale comparison with multiple agents
python examples/compare_agents_large_scale.py --num_requests 200 --num_vehicles 50
```

### 2. Run White Agents (Task Execution)

To implement and run a specific White Agent task locally:

```bash
# Run the custom agent example
python examples/custom_white_agent_example.py
```

### 3. Test Green Agent Evaluation

To verify the Green Agent's evaluation logic on specific test cases (functionality test):

```bash
# Run on a small set of 10 requests to verify parsing and scoring logic
python examples/demo_evaluation.py
```

## 🤖 AgentBeats Platform Deployment

To deploy your agents on the **AgentBeats v2 Platform** (`v2.agentbeats.org`) for official evaluation, follow these steps.

### Prerequisites

### Prerequisites

- Install `ngrok` and authenticate.
- Ensure two ngrok domains are reserved (e.g., `green.your-domain` and `white.your-domain`).

### Step 0: Setup Environment

Before running controllers, ensure dependencies are synced and the environment is active:

```bash
# Sync dependencies using uv
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### Step 1: Start Tunnels

Open two terminal windows to expose your local ports:

```bash
# Terminal 1: Green Agent Tunnel (Port 8010)
ngrok http 8010 --url=green.agentic-ai-taxi-routing.ngrok.com.ngrok.app

# Terminal 2: White Agent Tunnel (Port 8011)
ngrok http 8011 --url=white.agentic-ai-taxi-routing.ngrok.com.ngrok.app
```

### Step 2: Start Controllers

Open two new terminal windows to run the agent controllers. **Note**: They must run in separate directories.

- **Green Agent (Evaluator)** code is in `agentbeats_v2/`
- **White Agent (Subject)** code is in `agentbeats_v2_white/`

**Green Agent Controller (Evaluator)**:

```bash
# Terminal 3
cd agentbeats_v2

HTTPS_ENABLED=true \
PORT=8010 \
CLOUDRUN_HOST=green.agentic-ai-taxi-routing.ngrok.com.ngrok.app \
ROLE=green \
agentbeats run_ctrl
```

**White Agent Controller (Subject)**:

```bash
# Terminal 4
cd agentbeats_v2_white

HTTPS_ENABLED=true \
PORT=8011 \
CLOUDRUN_HOST=white.agentic-ai-taxi-routing.ngrok.com.ngrok.app \
ROLE=white \
agentbeats run_ctrl
```

### Step 3: Register Agents

1. Go to [v2.agentbeats.org](https://v2.agentbeats.org).
2. **Register Green Agent**:
   - **Name**: `greenagent`
   - **Deploy Type**: `Remote`
   - **Is Assessor**: ✅ Checked
   - **Controller URL**: `https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app` (No trailing path)
3. **Register White Agent**:
   - **Name**: `whiteagent`
   - **Deploy Type**: `Remote`
   - **Is Assessor**: ❌ Unchecked
   - **Controller URL**: `https://white.agentic-ai-taxi-routing.ngrok.com.ngrok.app`

### Step 4: Run Assessment

1. Click **Create Assessment** on the platform.
2. Select your registered Green Agent and White Agent.
3. Start the assessment and monitor the logs in your controller terminals.

For detailed troubleshooting and advanced testing, see the **[Full Deployment Guide](docs/guides/deployment_testing.md)**.

## 📚 Documentation

- **[Getting Started](docs/getting_started.md)**: Zero-to-hero guide to running your first evaluation.
- **[Framework Overview](docs/framework_overview.md)**: Deep dive into the system architecture and components.
- **[Component Guide](docs/guides/component_guide.md)**: Detailed API reference.
- **[Request Simulation Guide](docs/guides/request_simulation_quickstart.md)**: How to generate and customize synthetic requests.

## 🛠 Project Structure

```text
├── src/
│   ├── request_simulation/  # Natural language request generation
│   ├── vehicle_system/      # Fleet management and simulation
│   ├── white_agent/         # Dispatch agent interfaces
│   ├── evaluation/          # Scoring metrics
│   └── environment/         # Main simulation orchestrator
├── examples/                # Usage examples and demos
├── agentbeats_v2/           # Green Agent Controller (Evaluator) Code for Platform
├── agentbeats_v2_white/     # White Agent Controller (Subject) Code for Platform
├── docs/                    # Documentation and guides
└── tests/                   # Unit and integration tests
```

## 📅 Roadmap

Check the **[Implementation Roadmap](docs/implementation_roadmap.md)** for upcoming features and tasks.

## 📝 Release Notes

- **[Customer Profiles Update](docs/release_notes/customer_profiles_update.md)** (2025-12-14)
