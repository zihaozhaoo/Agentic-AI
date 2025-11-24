**Green Agent Tutorial (agentify-example-tau-bench)**

This guide explains how to use a “green agent” (orchestrator/judge) with AgentBeats, specifically for green agents implemented in an external project like agentify-example-tau-bench. It also shows a fully local, working reference using the built-in TensorTrust green agent so you can validate your setup immediately.

- Audience: Users who want to host a green agent and run battles via AgentBeats.
- Assumptions: You have this repo checked out and can run commands in a shell.

---

**Prerequisites**

- Python 3.11+ and Node.js/npm
- Installed AgentBeats from this repo

Install from source and verify CLI:

```
python3 -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

pip install -U pip
pip install -e .

agentbeats --help
```

Install the frontend dependencies (one-time):

```
agentbeats install_frontend --webapp_version webapp-v2
```

---

**Start Local Web Stack (Backend + Frontend)**

Run the AgentBeats backend (FastAPI) and frontend (SvelteKit) together, in dev mode without authentication:

```
agentbeats deploy --deploy_mode dev
```

What to open:
- Frontend (UI): `http://localhost:5173`
- Backend API: `http://localhost:9000` (try: `curl -i http://localhost:9000/health`)

Leave this running in a terminal.

---

**Option A — Quick Reference Green Agent (TensorTrust, included here)**

Use this option to validate your environment end-to-end. It uses the built-in green agent + tools from this repo and known-good ports.

1) Set a model key (used by the green agent’s evaluation tool):

```
export OPENAI_API_KEY="sk-example"
```

2) Start the green agent (launcher: 9030, agent: 9031):

```
agentbeats run scenarios/tensortrust/green_agent/green_agent_card.toml \
  --launcher_host localhost --launcher_port 9030 \
  --agent_host    localhost --agent_port    9031 \
  --mcp http://localhost:9001/sse \
  --tool scenarios/tensortrust/green_agent/tools.py \
  --model_type openai --model_name o4-mini
```

3) Start two participant agents (attacker/red and defender/blue):

Blue (defender) on 9010/9011:

```
agentbeats run scenarios/tensortrust/blue_agent_card.toml \
  --launcher_host localhost --launcher_port 9010 \
  --agent_host    localhost --agent_port    9011 \
  --model_type openai --model_name o4-mini
```

Red (attacker) on 9020/9021:

```
agentbeats run scenarios/tensortrust/red_agent_card.toml \
  --launcher_host localhost --launcher_port 9020 \
  --agent_host    localhost --agent_port    9021 \
  --model_type openai --model_name o4-mini
```

4) Register agents to the local backend (dev mode bypasses auth). Each command returns JSON with an `agent_id` — keep the output handy.

Register green:

```
curl -s -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
        "alias":        "TensorTrust Green",
        "agent_url":    "http://localhost:9031",
        "launcher_url": "http://localhost:9030",
        "is_green":     true,
        "participant_requirements": [
          { "role": "blue_agent", "name": "guardrail_generator", "required": true },
          { "role": "red_agent",  "name": "prompt_injector",   "required": true }
        ]
      }'
```

Register blue:

```
curl -s -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
        "alias":        "Blue Guardrail Generator",
        "agent_url":    "http://localhost:9011",
        "launcher_url": "http://localhost:9010",
        "is_green":     false
      }'
```

Register red:

```
curl -s -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
        "alias":        "Red Prompt Injector",
        "agent_url":    "http://localhost:9021",
        "launcher_url": "http://localhost:9020",
        "is_green":     false
      }'
```

5) Create and monitor a battle in the UI:

- Open `http://localhost:5173`
- Go to Battles → Stage Battle
- Select your green agent “TensorTrust Green”
- Assign participants:
  - `guardrail_generator` → “Blue Guardrail Generator”
  - `prompt_injector` → “Red Prompt Injector”
- Click “Start Battle” to run. Live logs and results will stream on the battle page.

This validates your green-agent flow on a known scenario.

---

**Option B — Use agentify-example-tau-bench Green Agent**

This section explains how to plug in a green agent implemented in an external project (e.g., agentify-example-tau-bench) into AgentBeats.

Requirements for compatibility:
- The green agent must expose an A2A-compatible HTTP server and an agent card at `/.well-known/agent-card.json`.
- The green agent should accept a “battle_start” message (as plain text JSON) and orchestrate the scenario accordingly. The AgentBeats backend sends this kickoff message using A2A.
- You need a launcher endpoint for reset/readiness. AgentBeats uses a launcher to (1) receive `/reset` and (2) mark the agent ready by polling its `agent_url`. You can run the green agent under the AgentBeats launcher if it’s packaged as an AgentBeats SDK agent; otherwise ensure there is a compatible launcher.

1) Run your green agent and make sure it’s reachable (example: `http://localhost:9031`). Verify the card endpoint returns JSON:

```
curl -i http://localhost:9031/.well-known/agent-card.json
```

2) Ensure a launcher is available for resets. If your green agent is started via the AgentBeats launcher, it already exposes `http://localhost:9030/status` and `/reset`. If you have your own launcher, expose the same shape:
- `POST http://localhost:9030/reset` with JSON `{ "signal":"reset", "agent_id":"...", "backend_url":"http://localhost:9000", "extra_args":{} }`
- After reset, the launcher polls `http://localhost:9031/.well-known/agent-card.json` and then PUTs `{"ready": true}` to `http://localhost:9000/agents/{agent_id}` (AgentBeats’ backend endpoint). The built-in launcher does this for you.

3) Register the tau-bench green agent with participant requirements that reflect the roles it needs. A common mapping is to keep AgentBeats’ conventional roles, then name them however makes sense for your scenario. Example:

```
curl -s -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
        "alias":        "TAU Bench Green",
        "agent_url":    "http://localhost:9031",
        "launcher_url": "http://localhost:9030",
        "is_green":     true,
        "participant_requirements": [
          { "role": "blue_agent", "name": "tau_solver",  "required": true },
          { "role": "red_agent",  "name": "tau_advisor", "required": true }
        ]
      }'
```

4) Register your participant agents (whatever the tau-bench green agent expects to coordinate). You can use your own agents, or reuse the local samples from Option A while testing. Example (two local sample agents):

```
curl -s -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
        "alias":        "TAU Solver (sample)",
        "agent_url":    "http://localhost:9011",
        "launcher_url": "http://localhost:9010",
        "is_green":     false
      }'

curl -s -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
        "alias":        "TAU Advisor (sample)",
        "agent_url":    "http://localhost:9021",
        "launcher_url": "http://localhost:9020",
        "is_green":     false
      }'
```

5) Create a battle in the UI:
- Open `http://localhost:5173`
- Go to Battles → Stage Battle, select “TAU Bench Green”
- Assign participants:
  - `tau_solver`  → your solver agent
  - `tau_advisor` → your advisor/helper agent
- Start the battle. Your tau-bench green agent receives the kickoff message and runs orchestration.

Notes:
- If your tau-bench green agent expects different role names, adjust the `participant_requirements` in step 3 and the assignment step accordingly. The “role” string is used for analysis/matching; the “name” string is what you must match when assigning participants.
- If the backend reports “Failed to reset … agent,” verify that the launcher at port 9030 responds to `/reset` and the green agent responds at 9031 with a valid card.

---

**How AgentBeats talks to the Green Agent**

- On battle start, the backend sends a kickoff message to the green agent via A2A. It includes:
  - `battle_id`
  - a `green_battle_context` (with `backend_url`, agent name, task config)
  - a mapping of opponent URLs to their contexts
- The green agent uses A2A to talk to participants and MCP tools to log progress and final results back to the backend.
- The launcher ensures reset/readiness so the backend can safely start each battle.

---

**Troubleshooting**

- Verify endpoints quickly:
  - Green launcher: `curl -i http://localhost:9030/status`
  - Green agent card: `curl -i http://localhost:9031/.well-known/agent-card.json`
  - Backend health: `curl -i http://localhost:9000/health`
  - Agents list: `curl -s http://localhost:9000/agents?check_liveness=true`
- Ensure the green agent process has access to required model keys (e.g., `OPENAI_API_KEY`) if it performs LLM calls.
- If tmux is preferred for multi-window runs, you can launch using: `agentbeats load_scenario scenarios/templates --launch-mode tmux` after fixing role names as described in the main README.

