## 2025-11-17 22:50 UTC

### Modified/Added Files
- `scenarios/function_exchange/scenario.toml`: Defines the complete wiring for the Function Exchange scenario with one green agent and one white agent plus the participant requirement that binds them.
- `scenarios/function_exchange/shared/functions_pool.py`: Provides the registered functions (sqrt_plus_constant, cube_minus_constant) along with helpers such as `choose_function`, `evaluate_function`, and `format_function_menu` for prompts/logging.
- `scenarios/function_exchange/shared/logging_utils.py`: Supplies `setup_component_logger` so each component writes to its own log file under `logs/`.
- `scenarios/function_exchange/shared/orchestration.py`: Implements `FunctionExchangeOrchestrator` which stores battle context, selects functions/x inputs, communicates with the white agent, and verifies the returned value.
- `scenarios/function_exchange/agents/green_agent/agent_card.toml` + `tools.py`: Card instructs the LLM to call `handle_incoming_message` then `start_function_exchange`; the tools bridge into the orchestrator with structured logging to `function_exchange_green_agent.log`.
- `scenarios/function_exchange/agents/white_agent/agent_card.toml` + `tools.py`: Card explains how to interpret the registry and respond with f(x) while the tools expose `list_registered_functions` plus `call_registered_function` and log to `function_exchange_white_agent.log`.

### Usage Guide
1. Ensure `OPENAI_API_KEY` is exported in your shell so both agents can use the OpenAI model declared in the cards (defaults to `o4-mini`).
2. Launch the scenario from the repo root:
   ```bash
   agentbeats load_scenario scenarios/function_exchange --launch-mode separate
   ```
   This spins up the two launchers/agents defined in `scenario.toml`. Use `--launch-mode tmux` if you prefer a single multiplexed terminal session.
3. Register the agents with your local backend (e.g., `http://localhost:9000`) via the UI or API, selecting the green agent “Function Exchange Green Agent” and assigning the participant slot `white_function_solver` to “Function Exchange White Agent”.
4. Start a battle from the UI (Stage Battle screen). Once the backend sends the `battle_start` message, the green agent’s `handle_incoming_message` tool seeds the orchestrator and each subsequent `start_function_exchange` call runs a verification round.
5. Review logs in:
   - `logs/function_exchange_orchestrator.log` – orchestration trace (function/x selection, verification results)
   - `logs/function_exchange_green_agent.log` – green agent tool invocations and errors
   - `logs/function_exchange_white_agent.log` – white agent function calls/registry lookups
6. To replay a specific combination deterministically for debugging, invoke the green agent tool with `function_name`, `x`, and/or `seed` via the AgentBeats UI console or CLI (e.g., `start_function_exchange(function_name="cube_minus_constant", x=3.5)`).

## 2025-11-17 23:09 UTC

### Modified/Added Files
- `src/agentbeats/utils/deploy/scenario_manager.py`: Relaxed the participant requirement validation so green agents can declare arbitrary role strings (any non-empty text) when defining participants.

### Usage Guide
The CLI `agentbeats load_scenario ...` command now supports scenario TOMLs where green agents declare custom participant roles (e.g., `function_solver`). No additional setup is required; re-run `agentbeats load_scenario scenarios/function_exchange --launch-mode separate` and the scenario will launch successfully as long as `OPENAI_API_KEY` remains configured.

## 2025-11-21 22:53 UTC

### Function Exchange: End-to-End Quickstart (CLI-only)
- **Prereqs**: Python env with AgentBeats installed, `OPENAI_API_KEY` exported, and `curl` available. Run all commands from the repo root (`~/agentbeats`).
- **1) Start backend + frontend (dev mode)**  
  ```bash
  agentbeats deploy --deploy_mode dev
  ```  
  Backend: `http://localhost:9000`, UI: `http://localhost:5173`.
- **2) Launch both agents (no xterm popups)**  
  Open a new terminal and run:  
  ```bash
  agentbeats load_scenario scenarios/function_exchange --launch-mode current
  ```  
  This starts the green/white launchers + agents on ports 9310/9311 and 9320/9321.
- **3) Register agents with the backend**  
  ```bash
  curl -s -X POST http://localhost:9000/agents \
    -H 'Content-Type: application/json' \
    -d '{
      "alias": "Function Exchange Green Agent",
      "agent_url": "http://localhost:9311",
      "launcher_url": "http://localhost:9310",
      "is_green": true,
      "participant_requirements": [
        { "role": "function_solver", "name": "white_function_solver", "required": true }
      ]
    }'

  curl -s -X POST http://localhost:9000/agents \
    -H 'Content-Type: application/json' \
    -d '{
      "alias": "Function Exchange White Agent",
      "agent_url": "http://localhost:9321",
      "launcher_url": "http://localhost:9320",
      "is_green": false
    }'
  ```  
  These calls return JSON; keep the `agent_id` values.
- **4) Start a battle (CLI)**  
  Use the IDs from step 3:  
  ```bash
  curl -s -X POST http://localhost:9000/battles \
    -H 'Content-Type: application/json' \
    -d '{"green_agent_id":"<GREEN_ID>","opponents":[{"name":"white_function_solver","agent_id":"<WHITE_ID>"}]}'
  ```  
  If you prefer the UI: open `http://localhost:5173/battles`, Stage Battle, pick “Function Exchange Green Agent”, and assign `white_function_solver` → “Function Exchange White Agent”.
- **5) Observe and debug**  
  - Live battle stream: `http://localhost:5173/battles`  
  - Logs: `logs/function_exchange_green_agent.log`, `logs/function_exchange_white_agent.log`, `logs/function_exchange_orchestrator.log`
- **What happens**: The green agent picks a registered function (`sqrt_plus_constant` or `cube_minus_constant`), sends x + the human description to the white agent, receives f(x), and checks it. Results are recorded to the backend and the log files above.

## 2025-12-10 22:41 UTC

### Modified/Added Files
- `src/request_simulation/request_simulator.py`: Added dense arrival rescheduling via `mean_interarrival_seconds` and optional `start_time`, plus shifted downstream timestamps so requests arrive in rapid succession while keeping pickup/dropoff windows consistent.
- `src/environment/green_agent_environment.py`: Seeded vehicles evenly across taxi zones, advanced the simulator clock between requests, and finalized trips asynchronously to keep cars busy until dropoff; exposed `prefer_uniform_distribution` and `mean_interarrival_seconds` hooks through `initialize_vehicles` and `generate_requests_from_data`.
- `src/vehicle_system/vehicle_simulator.py`: Advanced time now returns completed trips so the environment can free vehicles only after simulated dropoff.
- `examples/evaluate_baselines.py`: Baseline evaluation now uses the even vehicle spread and dense arrivals to mirror a high-utilization fleet.

### Usage Guide
- Run the baseline evaluation with busy-fleet settings (dense requests + even start layout):
  ```bash
  python3 examples/evaluate_baselines.py
  ```
- To generate busy-period requests elsewhere, pass `mean_interarrival_seconds` to the simulator helpers:
  ```python
  requests = environment.generate_requests_from_data(
      parquet_path="fhvhv_tripdata_2025-01.parquet",
      n_requests=500,
      augment_location=True,
      mean_interarrival_seconds=45.0,  # smaller means more overlap/busier vehicles
  )
  ```
- To seed a custom run with uniformly spread vehicles, rely on the defaults or set `prefer_uniform_distribution=True` when calling `initialize_vehicles`; set it to `False` only if you explicitly want clustered historical locations.

## 2025-12-10 23:11 UTC

### Modified/Added Files
- `src/request_simulation/request_simulator.py`: Added uniform pickup-zone sampling to flatten hotspot bias and lowered the default `mean_interarrival_seconds` to 15s so requests arrive fast enough to keep the fleet busy.
- `src/environment/green_agent_environment.py`: Broadened the even vehicle seeding to sample across borough footprints (not just borough centers) and exposed the uniform pickup sampling flag through `generate_requests_from_data`.
- `examples/evaluate_baselines.py`: Uses the new uniform pickup sampling with a tighter 12s interarrival to drive higher utilization during baseline runs.

### Usage Guide
- Run the baseline with denser demand and even vehicle seeding (no Google Maps calls):
  ```bash
  python3 examples/evaluate_baselines.py
  ```
- If you want to rebalance pickups elsewhere, call:
  ```python
  requests = environment.generate_requests_from_data(
      parquet_path="fhvhv_tripdata_2025-01.parquet",
      n_requests=2000,
      augment_location=False,
      mean_interarrival_seconds=12.0,   # smaller → busier
      uniform_zone_sampling=True        # flatten pickup hotspots
  )
  ```
- Vehicle initialization stays even by default (`prefer_uniform_distribution=True`); keep it enabled to avoid starting clusters, or set to `False` only when you intentionally want historical clustering.

## 2025-12-11 16:21 UTC

### Modified/Added Files
- `src/environment/green_agent_environment.py`: Tightened borough bounding boxes and jitter to keep seeded vehicles on land and closer to demand; retained even distribution across zones.
- `src/vehicle_system/vehicle_database.py`: When initial locations are provided, vehicles now round-robin through those coordinates with slight jitter instead of random re-sampling, preventing clusters and water spawns.

### Usage Guide
- Regenerate requests and rerun baselines after these fixes to re-seed vehicles on land:
  ```bash
  python3 examples/evaluate_baselines.py
  ```
