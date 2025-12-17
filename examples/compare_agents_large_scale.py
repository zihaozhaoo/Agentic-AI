"""
Large-scale comparison: NaturalLanguageAgent vs DummyWhiteAgent vs RegexBaselineAgent.

Default experiment:
- 200 simulated requests
- 50 vehicles

This script runs the same request set against each agent and writes:
- `results/experiments/<run_id>/<agent>.json` (evaluation results)
- `results/experiments/<run_id>/requests.json` (the generated requests)
- `logs/visualizations/<run_id>/<agent>/` (events + trajectories + HTML map)

Notes:
- NaturalLanguageAgent requires `OPENAI_API_KEY` and `GOOGLE_MAPS_API_KEY`.
- If `--augment_location` is enabled, request generation also uses Google Maps.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

# Add src/ to import path (matches other examples)
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from request_simulation import RequestSimulator  # noqa: E402
from environment import GreenAgentEnvironment  # noqa: E402
from utils import EventLogger  # noqa: E402
from white_agent import (  # noqa: E402
    DummyWhiteAgent,
    RegexBaselineAgent,
    NaturalLanguageAgent,
)


def _set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


@dataclass
class AgentRunResult:
    agent_label: str
    agent_name: str
    results_path: Path
    viz_dir: Path
    summary: dict[str, Any]


def _build_agent(agent_key: str, request_simulator: RequestSimulator):
    if agent_key == "natural":
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("Missing OPENAI_API_KEY (required for NaturalLanguageAgent).")
        if not os.environ.get("GOOGLE_MAPS_API_KEY"):
            raise SystemExit("Missing GOOGLE_MAPS_API_KEY (required for NaturalLanguageAgent).")
        return NaturalLanguageAgent(
            agent_name="NaturalLanguageAgent",
            customer_db=request_simulator.customer_db,
        )
    if agent_key == "dummy":
        return DummyWhiteAgent(
            agent_name="DummyWhiteAgent",
            customer_db=request_simulator.customer_db,
        )
    if agent_key == "regex":
        return RegexBaselineAgent(
            agent_name="RegexBaselineAgent",
            customer_db=request_simulator.customer_db,
        )
    raise ValueError(f"Unknown agent_key: {agent_key}")


def _print_comparison(results: list[AgentRunResult]) -> None:
    rows = []
    for r in results:
        summary = r.summary
        parsing = summary.get("parsing_metrics", {})
        routing = summary.get("routing_metrics", {})
        rows.append(
            {
                "Agent": r.agent_name,
                "Score": summary.get("overall_score", 0.0),
                "OriginAcc": parsing.get("origin_zone_accuracy", 0.0) * 100.0,
                "DestAcc": parsing.get("destination_zone_accuracy", 0.0) * 100.0,
                "Deadhead": routing.get("deadhead_ratio", 0.0) * 100.0,
                "Rev/Mile": routing.get("revenue_per_mile", 0.0),
                "Requests": summary.get("total_requests_evaluated", 0),
            }
        )

    # Simple fixed-width table (no external deps)
    print("\n" + "=" * 96)
    print("FINAL COMPARISON")
    print("=" * 96)
    header = f"{'Agent':22} | {'Score':>7} | {'OriginAcc%':>10} | {'DestAcc%':>9} | {'Deadhead%':>9} | {'Rev/Mile':>8} | {'EvalN':>5}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['Agent'][:22]:22} | "
            f"{row['Score']:7.2f} | "
            f"{row['OriginAcc']:10.1f} | "
            f"{row['DestAcc']:9.1f} | "
            f"{row['Deadhead']:9.2f} | "
            f"{row['Rev/Mile']:8.2f} | "
            f"{row['Requests']:5d}"
        )
    print("=" * 96)


def main() -> None:
    parser = argparse.ArgumentParser(description="Large-scale evaluation of three white agents.")
    parser.add_argument("--num_requests", type=int, default=200)
    parser.add_argument("--num_vehicles", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--template_ratio", type=float, default=1.0, help="0..1; 1.0 = template-only requests")
    parser.add_argument(
        "--augment_location",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="If true, request generation uses Google Maps to add street-level coords.",
    )
    parser.add_argument(
        "--mean_interarrival_seconds",
        type=str,
        default="15.0",
        help="Lower means more demand/overlap; use 'none' to keep original dataset times.",
    )
    parser.add_argument(
        "--prefer_uniform_fleet",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="If true, seed vehicles evenly across zones (ignores parquet sampling).",
    )
    parser.add_argument("--fleet_sample_size", type=int, default=500, help="Only used if --prefer_uniform_fleet is false.")
    parser.add_argument("--natural_delay_s", type=float, default=0.0, help="Optional sleep between requests for NaturalLanguageAgent.")
    args = parser.parse_args()

    if not (0.0 <= args.template_ratio <= 1.0):
        raise SystemExit("--template_ratio must be between 0.0 and 1.0")

    mean_interarrival_seconds = args.mean_interarrival_seconds.strip().lower()
    mean_interarrival_value = None if mean_interarrival_seconds in ("none", "null") else float(mean_interarrival_seconds)

    project_root = Path(__file__).parent.parent
    parquet_file = project_root / "fhvhv_tripdata_2025-01.parquet"
    taxi_zone_lookup = project_root / "taxi_zone_lookup.csv"

    run_id = datetime.now().strftime("exp_%Y%m%d_%H%M%S") + f"_n{args.num_requests}_v{args.num_vehicles}"
    results_root = project_root / "results" / "experiments" / run_id
    viz_root = project_root / "logs" / "visualizations" / run_id
    _ensure_dir(results_root)
    _ensure_dir(viz_root)

    print(f"Run ID: {run_id}")
    print(f"Results: {results_root}")
    print(f"Viz:     {viz_root}")
    print()

    # Deterministic request generation.
    _set_seeds(args.seed)
    request_simulator = RequestSimulator(
        taxi_zone_lookup_path=str(taxi_zone_lookup),
        template_ratio=float(args.template_ratio),
    )
    # Generate once; reuse across agents.
    gen_logger = EventLogger(
        log_file_path=str(results_root / "request_generation.log"),
        console_level=logging.WARNING,
        file_level=logging.INFO,
        enable_json_log=False,
    )
    gen_env = GreenAgentEnvironment(request_simulator=request_simulator, logger=gen_logger)
    requests = gen_env.generate_requests_from_data(
        parquet_path=str(parquet_file),
        n_requests=int(args.num_requests),
        augment_location=bool(args.augment_location),
        mean_interarrival_seconds=mean_interarrival_value,
        uniform_zone_sampling=True,
    )
    request_simulator.save_requests(requests, str(results_root / "requests.json"))

    agents_to_run = [
        ("natural", "NaturalLanguageAgent"),
        ("dummy", "DummyWhiteAgent"),
        ("regex", "RegexBaselineAgent"),
    ]

    all_results: list[AgentRunResult] = []
    for agent_key, agent_label in agents_to_run:
        print("\n" + "=" * 80)
        print(f"Running agent: {agent_label}")
        print("=" * 80)

        # Reset RNG before fleet init so all agents start from the same fleet state.
        _set_seeds(args.seed)

        agent_slug = agent_label.lower()
        agent_results_path = results_root / f"{agent_slug}.json"
        agent_viz_dir = viz_root / agent_slug
        _ensure_dir(agent_viz_dir)

        logger = EventLogger(
            log_file_path=str(agent_viz_dir / "evaluation.log"),
            console_level=logging.WARNING,
            file_level=logging.DEBUG,
            enable_json_log=True,
        )
        env = GreenAgentEnvironment(request_simulator=request_simulator, logger=logger)

        env.initialize_vehicles(
            num_vehicles=int(args.num_vehicles),
            sample_parquet_path=str(parquet_file),
            sample_size=int(args.fleet_sample_size),
            prefer_uniform_distribution=bool(args.prefer_uniform_fleet),
        )

        white_agent = _build_agent(agent_key, request_simulator)
        delay = float(args.natural_delay_s) if agent_key == "natural" else 0.0

        t0 = time.time()
        results = env.run_evaluation(
            white_agent=white_agent,
            requests=requests,
            verbose=False,
            map_output_dir=str(agent_viz_dir),
            inter_request_delay_seconds=delay,
        )
        elapsed_s = time.time() - t0

        env.save_results(results, str(agent_results_path))
        summary = results.get("evaluation_summary", {})
        summary = {**summary, "wall_time_seconds": elapsed_s}

        all_results.append(
            AgentRunResult(
                agent_label=agent_label,
                agent_name=results.get("agent_name", agent_label),
                results_path=agent_results_path,
                viz_dir=agent_viz_dir,
                summary=summary,
            )
        )

    _print_comparison(all_results)

    combined = {
        "run_id": run_id,
        "config": {
            "num_requests": args.num_requests,
            "num_vehicles": args.num_vehicles,
            "seed": args.seed,
            "template_ratio": args.template_ratio,
            "augment_location": args.augment_location,
            "mean_interarrival_seconds": mean_interarrival_value,
            "prefer_uniform_fleet": args.prefer_uniform_fleet,
            "fleet_sample_size": args.fleet_sample_size,
            "natural_delay_s": args.natural_delay_s,
        },
        "agents": [
            {
                "agent_name": r.agent_name,
                "agent_label": r.agent_label,
                "results_json": str(r.results_path),
                "viz_dir": str(r.viz_dir),
                "summary": r.summary,
            }
            for r in all_results
        ],
    }
    (results_root / "summary.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(f"\nWrote combined summary: {results_root / 'summary.json'}")


if __name__ == "__main__":
    main()
