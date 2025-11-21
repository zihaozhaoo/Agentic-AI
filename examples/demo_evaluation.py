"""
Demo: Green Agent Evaluation Framework

This script demonstrates how to use the Green Agent framework to evaluate
a white agent on the ride-hailing dispatch task.
"""

import sys
from pathlib import Path
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from request_simulation import RequestSimulator
from white_agent import DummyWhiteAgent
from environment import GreenAgentEnvironment
from utils import EventLogger
from google_map.gmap import create_distance_calculator

# Google Maps API Key - Replace with your actual key
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY_HERE"


def main():
    """
    Demo: Evaluate a white agent on ride-hailing dispatch task.
    """

    print("="*80)
    print("GREEN AGENT EVALUATION FRAMEWORK - DEMO")
    print("="*80)
    print()

    # =========================================================================
    # STEP 1: Initialize Request Simulator
    # =========================================================================
    print("Step 1: Initializing Request Simulator...")
    print("-" * 80)

    # Get absolute paths
    project_root = Path(__file__).parent.parent
    taxi_zone_lookup = str(project_root / "taxi_zone_lookup.csv")

    request_simulator = RequestSimulator(
        taxi_zone_lookup_path=taxi_zone_lookup,
        template_ratio=1.0,  # Use 100% templates (no LLM) for demo
    )

    print("✓ Request Simulator initialized\n")

    # =========================================================================
    # STEP 2: Initialize Logger
    # =========================================================================
    print("Step 2: Initializing Event Logger...")
    print("-" * 80)

    # Create logger with file output
    logger = EventLogger(
        log_file_path=str(project_root / "logs" / "evaluation.log"),
        console_level=logging.WARNING,  # Only show warnings/errors in console
        file_level=logging.DEBUG,  # Log everything to file
        enable_json_log=True  # Enable JSON event log
    )

    print("✓ Event Logger initialized\n")

    # =========================================================================
    # STEP 3: Initialize Green Agent Environment
    # =========================================================================
    print("Step 3: Initializing Green Agent Environment...")
    print("-" * 80)

    # Create distance calculator with Google Maps API
    # Set use_google_maps=True and provide your API key for actual travel times
    use_google_maps = False  # Set to True to use Google Maps API
    distance_calculator = None

    if use_google_maps:
        if GOOGLE_MAPS_API_KEY != "YOUR_GOOGLE_MAPS_API_KEY_HERE":
            distance_calculator = create_distance_calculator(GOOGLE_MAPS_API_KEY)
            print("  ✓ Google Maps distance calculator enabled")
        else:
            print("  ⚠ Google Maps API key not set, using fallback estimates")

    environment = GreenAgentEnvironment(
        request_simulator=request_simulator,
        distance_calculator=distance_calculator,  # Pass distance calculator for actual travel times
        logger=logger
    )

    print("✓ Environment initialized\n")

    # =========================================================================
    # STEP 4: Initialize Vehicle Fleet
    # =========================================================================
    print("Step 4: Initializing Vehicle Fleet...")
    print("-" * 80)

    # Get parquet file path (needed for vehicle initialization)
    parquet_file = str(project_root / "fhvhv_tripdata_2025-01.parquet")

    # Initialize 100 vehicles (small fleet for demo)
    # Sample from actual trip data for realistic locations
    environment.initialize_vehicles(
        num_vehicles=100,
        wheelchair_accessible_ratio=0.1,
        sample_parquet_path=parquet_file,  # Use same data file
        sample_size=1000  # Sample 1000 trips for location distribution
    )

    print("✓ Vehicle fleet initialized\n")

    # =========================================================================
    # STEP 5: Generate Requests
    # =========================================================================
    print("Step 5: Generating Requests from Trip Data...")
    print("-" * 80)

    # Generate 10 requests for demo (increase for real evaluation)
    requests = environment.generate_requests_from_data(
        parquet_path=parquet_file,
        n_requests=10,
        augment_location=False  # Set to True to use Google Maps API
    )

    print(f"✓ Generated {len(requests)} requests\n")

    # Print example requests
    print("Example requests:")
    for i, req in enumerate(requests[:3]):
        print(f"\n  Request {i+1}:")
        print(f"    From: {req.get('pickup_zone', 'Unknown')}")
        print(f"    To: {req.get('dropoff_zone', 'Unknown')}")
        print(f"    Text: {req.get('request', 'N/A')[:100]}...")

    print()

    # =========================================================================
    # STEP 6: Initialize White Agent
    # =========================================================================
    print("Step 6: Initializing White Agent...")
    print("-" * 80)

    # Use dummy agent for demo
    # In actual evaluation, replace with your custom white agent
    white_agent = DummyWhiteAgent(
        agent_name="DemoAgent",
        config={"version": "1.0"}
    )

    print(f"✓ White Agent '{white_agent.agent_name}' initialized\n")

    # =========================================================================
    # STEP 7: Run Evaluation
    # =========================================================================
    print("Step 7: Running Evaluation...")
    print("-" * 80)

    results = environment.run_evaluation(
        white_agent=white_agent,
        requests=requests,
        verbose=True
    )

    # =========================================================================
    # STEP 8: Save Results
    # =========================================================================
    print("\nStep 8: Saving Results...")
    print("-" * 80)

    # Save evaluation results
    output_path = str(project_root / "results" / "demo_evaluation.json")
    environment.save_results(results, output_path)

    # Save event log
    log_output_path = str(project_root / "logs" / "events.json")
    logger.save_json_log(log_output_path)

    print("✓ Results saved\n")
    print(f"  - Evaluation results: {output_path}")
    print(f"  - Event log: {log_output_path}")
    print(f"  - Text log: {project_root / 'logs' / 'evaluation.log'}")
    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print()
    print("Next Steps:")
    print("  1. Implement your own WhiteAgent by inheriting from WhiteAgentBase")
    print("  2. Implement parse_request() and make_routing_decision() methods")
    print("  3. Run evaluation with larger dataset (100K+ requests)")
    print("  4. Compare your agent against baselines")
    print()
    print("Key Files:")
    print(f"  - Results: {output_path}")
    print(f"  - White Agent Interface: src/white_agent/base_agent.py")
    print(f"  - Data Structures: src/white_agent/data_structures.py")
    print()


if __name__ == "__main__":
    main()
