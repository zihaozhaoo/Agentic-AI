# AgentBeats v2 (A2A) Wrapper for Our Ride-Hailing Baselines

This folder shows how to run the existing ride-hailing baselines (dummy, regex, random, nearest-vehicle) through the AgentBeats **v2** A2A interface, mirroring the `agentify-example-tau-bench` sample.

## What changed from v1 to v2?

- **Protocol first**: v2 uses the Agent-to-Agent (A2A) HTTP interface (Starlette app + agent card) instead of the custom local runner in v1.
- **Agents are HTTP services**: green/white agents expose `/agent.json` cards and `/messages` endpoints; the launcher talks to them over HTTP via the A2A client.
- **Task handoff is text-based**: the launcher sends a single instruction blob to the green agent; all coordination (evaluation, downstream calls) happens inside the green agent service.
- **Composable with other A2A/MCP tools**: agents can be swapped/stacked by URL; no tight coupling to the Python runtime of the evaluator.

## Layout

```
agentbeats_v2/
  main.py           # Typer CLI (green/white/launch)
  launcher.py       # Starts services and sends a task to green
  src/
    green_agent/
      agent.py      # Runs the ride-hailing evaluation when messaged
      tau_green_agent.toml
    white_agent/
      agent.py      # Simple LLM-backed echo white agent (for completeness)
      general_white_agent.toml
    my_util/
      my_a2a.py     # A2A client helpers (copied from tau-bench sample)
```

## Prerequisites

- Python 3.11+
- Install repo deps (from repo root):
  ```bash
  pip install -e .
  pip install uvicorn typer httpx litellm
  ```
- Data files present at the repo root:
  - `taxi_zone_lookup.csv`
  - `fhvhv_tripdata_2025-01.parquet` (used for sampling trips/vehicles)
- Environment: `OPENAI_API_KEY` for the sample white agent LLM (green agent uses only local computation for baselines).

## Run (full v2 flow)

From `agentbeats_v2/`:
```bash
export OPENAI_API_KEY=sk-...  # for the sample white agent (not used by baselines)
python main.py launch
```

What happens:
1) `launch` spins up the green agent (port 9101) and the sample white agent (port 9102).  
2) The launcher sends a task text to the green agent specifying which baseline to run (default: `nearest`).  
3) The green agent runs the ride-hailing evaluation using our existing environment (`src/environment/green_agent_environment.py`) and baselines, then replies with metrics.  
4) Processes terminate after the run.

## Run agents separately
```bash
# Green agent only
python main.py green

# White agent only (LLM echo)
python main.py white
```
Then send a message to the green agent via an A2A client (see `launcher.py` for an example payload).

## Changing the baseline

The launcher message contains a tag `<agent_name>...</agent_name>`; supported values:
- `dummy`
- `regex`
- `random`
- `nearest` (default; lowest deadhead)

## Expected output

The green agent responds with:
- Overall score (using the current scoring logic in `Evaluator`)
- Deadhead ratio, revenue per mile
- Paths to trajectories JSON/HTML exported under `logs/visualizations/`

You can open the HTML to visualize vehicle movements. The map UI includes Play/Next/Reset controls and shows total deadhead and trip miles.

## Deploying on v2.agentbeats.org (from Notes.pdf)

1) **Prereqs**
   - Domain or Cloudflare tunnel for HTTPS (platform prefers HTTPS URLs).
   - Env vars:  
     - `PUBLIC_URL`: externally reachable URL for this agent (e.g., `https://yourdomain/green`)  
     - `AGENT_HOST`/`AGENT_PORT`: bind address/port (default `0.0.0.0` / `8010` for cloudflared).  
   - `OPENAI_API_KEY` for the sample white agent.

2) **Run controllers (green/white)**
   - Green:
     ```bash
     cd agentbeats_v2
     PUBLIC_URL=https://yourdomain/green AGENT_HOST=0.0.0.0 AGENT_PORT=8010 \
     python main.py green
     ```
   - White (optional echo agent):
     ```bash
     PUBLIC_URL=https://yourdomain/white AGENT_HOST=0.0.0.0 AGENT_PORT=8011 \
     python main.py white
     ```
   - Expose them via Cloudflare Tunnel or your ingress so the URLs are reachable.

3) **Register agents on the platform**
   - Visit `https://v2.agentbeats.org`, log in with GitHub.
   - “Register agent” → paste the public `PUBLIC_URL` for green; repeat for white if you want it discoverable.
   - Verify the agent card loads (agent check passes).

4) **Create an assessment**
   - After registering, “Create assessment” and select the green agent (and the white agent URL if you want remote parsing).  
   - For our harness, you can include `<white_agent_url>` in the task message to force remote parsing; otherwise the green agent uses local baselines.

5) **Monitor**
   - Watch the assessment logs; check task return & agent logs. Visualizations and metrics are written under `logs/visualizations/` on the host.

6) **Sharing**
   - Use the platform’s share link for the assessment once logs look good.

Notes:
- The green/white agent cards now include required `capabilities` and `skills` for platform validation.
- `PUBLIC_URL` is written into the AgentCard at startup; set it to the externally reachable HTTPS URL the platform will probe.
