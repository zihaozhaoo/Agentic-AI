"""
Baseline Evaluation Script

This script evaluates the baseline agents (Dummy, Regex, Random) using real trip data.
"""

import sys
from pathlib import Path
import logging
import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from request_simulation import RequestSimulator
from white_agent import DummyWhiteAgent, RegexBaselineAgent, RandomBaselineAgent
from environment import GreenAgentEnvironment
from utils import EventLogger

def main():
    print("="*80)
    print("BASELINE AGENT EVALUATION")
    print("="*80)
    print()

    # Setup paths
    project_root = Path(__file__).parent.parent
    taxi_zone_lookup = str(project_root / "taxi_zone_lookup.csv")
    parquet_file = str(project_root / "fhvhv_tripdata_2025-01.parquet")
    
    # Initialize components
    print("Initializing Environment...")
    request_simulator = RequestSimulator(
        taxi_zone_lookup_path=taxi_zone_lookup,
        template_ratio=1.0 # Use templates for consistent testing
    )
    
    logger = EventLogger(
        log_file_path=str(project_root / "logs" / "baseline_eval.log"),
        console_level=logging.WARNING
    )
    
    environment = GreenAgentEnvironment(
        request_simulator=request_simulator,
        logger=logger
    )
    
    # Initialize Fleet
    print("Initializing Fleet...")
    environment.initialize_vehicles(
        num_vehicles=50,
        sample_parquet_path=parquet_file,
        sample_size=200
    )
    
    # Generate Requests
    print("Generating Requests...")
    requests = environment.generate_requests_from_data(
        parquet_path=parquet_file,
        n_requests=50, # 50 requests for quick evaluation
        augment_location=False
    )
    print(f"Generated {len(requests)} requests.")
    
    # Define Agents to Test
    agents = [
        DummyWhiteAgent(agent_name="DummyAgent (Test)"),
        RegexBaselineAgent(agent_name="RegexBaseline"),
        RandomBaselineAgent(agent_name="RandomBaseline")
    ]
    
    results_summary = []
    
    # Run Evaluation Loop
    for agent in agents:
        print(f"\nRunning Evaluation for {agent.agent_name}...")
        try:
            result = environment.run_evaluation(
                white_agent=agent,
                requests=requests,
                verbose=False # Reduce verbosity for batch run
            )
            
            summary = result['evaluation_summary']
            parsing = summary['parsing_metrics']
            routing = summary['routing_metrics']
            
            results_summary.append({
                'name': agent.agent_name,
                'score': summary['overall_score'],
                'origin_acc': parsing['origin_zone_accuracy'],
                'dest_acc': parsing['destination_zone_accuracy'],
                'rev_per_mile': routing['revenue_per_mile']
            })
            
            print(f"  Score: {summary['overall_score']:.2f}")
            print(f"  Origin Acc: {parsing['origin_zone_accuracy']*100:.1f}%")
            print(f"  Dest Acc: {parsing['destination_zone_accuracy']*100:.1f}%")
            
        except Exception as e:
            print(f"  Failed: {e}")
            import traceback
            traceback.print_exc()

    # Print Final Comparison Table
    print("\n" + "="*80)
    print("FINAL COMPARISON")
    print("="*80)
    print(f"{'Agent Name':<20} | {'Score':<8} | {'Origin Acc':<12} | {'Dest Acc':<12} | {'Rev/Mile':<10}")
    print("-" * 70)
    
    for res in results_summary:
        print(f"{res['name']:<20} | {res['score']:<8.2f} | {res['origin_acc']*100:<11.1f}% | {res['dest_acc']*100:<11.1f}% | ${res['rev_per_mile']:<9.2f}")
    print("-" * 70)

if __name__ == "__main__":
    main()
