#!/usr/bin/env python3
"""
Example script demonstrating how to use the Request Simulation module.

This script:
1. Loads and preprocesses NYC taxi trip data
2. Generates synthetic customer profiles and POI database
3. Simulates natural language ride requests using templates and LLMs
4. Saves the results to JSON
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.request_simulation import RequestSimulator
import yaml


def load_config(config_path: str = "configs/request_simulation.yaml"):
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Main execution function."""

    print("="*80)
    print("NYC RIDE REQUEST SIMULATOR")
    print("="*80)
    print()

    # Load configuration
    config = load_config()

    # Paths
    taxi_zone_lookup = config['data']['taxi_zone_lookup']
    parquet_file = config['data']['parquet_file']
    output_dir = Path(config['data']['output_dir'])
    cache_dir = Path(config['data']['cache_dir'])

    # Create directories
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Initialize simulator
    print("Initializing Request Simulator...")
    simulator = RequestSimulator(
        taxi_zone_lookup_path=taxi_zone_lookup,
        google_maps_api_key=config['api_keys'].get('google_maps'),
        llm_provider=config['nl_generation']['llm_provider'],
        llm_api_key=config['api_keys'].get(config['nl_generation']['llm_provider']),
        use_location_cache=config['location_augmentation']['use_cache'],
        template_ratio=config['nl_generation']['template_ratio']
    )

    # Update template tier probabilities
    simulator.template_gen.tier_probabilities = config['template_tiers']

    # Load and preprocess data
    print("\n" + "-"*80)
    print("STEP 1: Data Preprocessing")
    print("-"*80)

    df = simulator.load_and_preprocess_data(
        parquet_file,
        sample_size=config['preprocessing']['sample_size']
    )

    # Generate customer profiles
    print("\n" + "-"*80)
    print("STEP 2: Customer Profile Generation")
    print("-"*80)

    print(f"Generating {config['customer_profiles']['num_profiles']} customer profiles...")
    simulator.customer_db.generate_profiles(config['customer_profiles']['num_profiles'])

    if config['simulation']['save_intermediate']:
        customer_file = cache_dir / "customer_profiles.json"
        simulator.customer_db.save_to_json(str(customer_file))

    # Save POI database
    if config['simulation']['save_intermediate']:
        poi_file = cache_dir / "poi_database.json"
        simulator.poi_db.save_to_json(str(poi_file))

    # Simulate requests
    print("\n" + "-"*80)
    print("STEP 3: Natural Language Request Generation")
    print("-"*80)

    output_file = output_dir / f"simulated_requests.{config['simulation']['output_format']}"

    requests = simulator.simulate_requests(
        df,
        n_requests=config['simulation']['n_requests'],
        augment_location=config['location_augmentation']['enabled'],
        save_output=str(output_file)
    )

    # Print statistics
    print("\n" + "="*80)
    print("SIMULATION STATISTICS")
    print("="*80)

    stats = simulator.get_statistics(requests)

    print(f"\nTotal Requests: {stats['total_requests']}")

    print(f"\nGeneration Methods:")
    for method, count in stats['generation_methods'].items():
        pct = (count / stats['total_requests']) * 100
        print(f"  {method}: {count} ({pct:.1f}%)")

    if stats['template_tiers']:
        print(f"\nTemplate Tiers:")
        for tier, count in stats['template_tiers'].items():
            pct = (count / sum(stats['template_tiers'].values())) * 100
            print(f"  {tier}: {count} ({pct:.1f}%)")

    # Print some example requests
    print("\n" + "="*80)
    print("EXAMPLE REQUESTS")
    print("="*80)

    import random
    for i, req in enumerate(random.sample(requests, min(10, len(requests)))):
        print(f"\n--- Request {i+1} ---")
        print(f"Method: {req.get('generation_method', 'unknown')}")
        if req.get('tier'):
            print(f"Tier: {req.get('tier')}")
        print(f"\nRequest: \"{req.get('request', 'N/A')}\"")
        print(f"\nDetails:")
        print(f"  From: {req.get('pickup_zone', 'Unknown')} ({req.get('pickup_borough', 'Unknown')})")
        print(f"  To: {req.get('dropoff_zone', 'Unknown')} ({req.get('dropoff_borough', 'Unknown')})")
        print(f"  Time: {req.get('request_time', 'Unknown')}")

        if req.get('pickup_personal'):
            print(f"  Personal reference: {req.get('pickup_personal')}")

    print("\n" + "="*80)
    print("SIMULATION COMPLETE!")
    print(f"Output saved to: {output_file}")
    print("="*80)


if __name__ == "__main__":
    main()
