#!/usr/bin/env python3
"""
Demo: Time Windows and Arrival Constraints

This script demonstrates the new time window features:
- Pickup time windows
- Arrival time constraints
- Tight vs. loose time constraints
- Natural language generation with time information
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.request_simulation import (
    TemplateGenerator,
    LLMGenerator
)


def demo_template_generation():
    """Demo template-based generation with time windows."""

    print("="*80)
    print("DEMO: Template-Based Generation with Time Windows")
    print("="*80)
    print()

    generator = TemplateGenerator()

    # Example 1: Basic request with pickup time
    print("--- Example 1: Basic Request with Pickup Time ---")
    trip_data_1 = {
        'pickup_zone': 'Times Square',
        'dropoff_zone': 'Central Park',
        'requested_pickup_time': datetime(2025, 1, 15, 14, 30),
        'pickup_window_minutes': 15,
        'request_time': datetime(2025, 1, 15, 14, 30),
    }

    result = generator.generate(trip_data_1, tier='basic')
    print(f"Request: \"{result['request']}\"")
    print(f"Pickup: {trip_data_1['requested_pickup_time'].strftime('%I:%M %p')}")
    print(f"Window: ±{trip_data_1['pickup_window_minutes']} minutes")
    print()

    # Example 2: Time-constrained request with arrival time
    print("--- Example 2: Time-Constrained Request ---")
    trip_data_2 = {
        'pickup_zone': 'Upper West Side',
        'dropoff_zone': 'JFK Airport',
        'pickup_poi': None,
        'dropoff_poi': 'JFK',
        'requested_pickup_time': datetime(2025, 1, 15, 14, 0),
        'requested_dropoff_time': datetime(2025, 1, 15, 16, 30),
        'pickup_window_minutes': 10,
        'dropoff_window_minutes': 10,
        'has_arrival_constraint': True,
        'is_tight_constraint': False,
        'available_trip_time_minutes': 150,
        'actual_trip_duration_minutes': 120,
        'estimated_duration_minutes': 120,
        'request_time': datetime(2025, 1, 15, 14, 0),
    }

    result = generator.generate(trip_data_2, tier='time_constrained')
    print(f"Request: \"{result['request']}\"")
    print(f"Pickup: {trip_data_2['requested_pickup_time'].strftime('%I:%M %p')}")
    print(f"Arrival: {trip_data_2['requested_dropoff_time'].strftime('%I:%M %p')}")
    print(f"Available time: {trip_data_2['available_trip_time_minutes']:.0f} minutes")
    print(f"Estimated duration: {trip_data_2['estimated_duration_minutes']:.0f} minutes")
    print(f"Tight constraint: {trip_data_2['is_tight_constraint']}")
    print()

    # Example 3: TIGHT time constraint (urgent)
    print("--- Example 3: Tight Time Constraint (Urgent) ---")
    trip_data_3 = {
        'pickup_zone': 'Midtown',
        'dropoff_zone': 'LaGuardia Airport',
        'pickup_poi': 'Times Square',
        'dropoff_poi': 'LaGuardia',
        'requested_pickup_time': datetime(2025, 1, 15, 15, 0),
        'requested_dropoff_time': datetime(2025, 1, 15, 15, 50),
        'pickup_window_minutes': 5,
        'dropoff_window_minutes': 5,
        'has_arrival_constraint': True,
        'is_tight_constraint': True,  # Available time < needed time
        'available_trip_time_minutes': 50,
        'actual_trip_duration_minutes': 45,
        'estimated_duration_minutes': 45,
        'request_time': datetime(2025, 1, 15, 15, 0),
    }

    result = generator.generate(trip_data_3, tier='time_constrained')
    print(f"Request: \"{result['request']}\"")
    print(f"Pickup: {trip_data_3['requested_pickup_time'].strftime('%I:%M %p')}")
    print(f"Arrival: {trip_data_3['requested_dropoff_time'].strftime('%I:%M %p')}")
    print(f"Available time: {trip_data_3['available_trip_time_minutes']:.0f} minutes")
    print(f"Estimated duration: {trip_data_3['estimated_duration_minutes']:.0f} minutes")
    print(f"Margin: {trip_data_3['available_trip_time_minutes'] - trip_data_3['estimated_duration_minutes']:.0f} minutes")
    print(f"Tight constraint: {trip_data_3['is_tight_constraint']}")
    print()

    # Example 4: Multiple variations
    print("--- Example 4: Multiple Variations of Same Trip ---")
    for i in range(3):
        result = generator.generate(trip_data_2, tier='time_constrained')
        print(f"{i+1}. \"{result['request']}\"")
    print()


def demo_llm_generation():
    """Demo LLM-based generation with time windows."""

    print("="*80)
    print("DEMO: LLM-Based Generation with Time Windows")
    print("="*80)
    print()

    try:
        # Try OpenAI
        print("Attempting to use OpenAI GPT...")
        llm_gen = LLMGenerator(provider="openai")

        trip_data = {
            'pickup_zone': 'Upper West Side',
            'dropoff_zone': 'Brooklyn Heights',
            'pickup_personal': 'home',
            'dropoff_personal': 'work',
            'requested_pickup_time': datetime(2025, 1, 15, 8, 30),
            'requested_dropoff_time': datetime(2025, 1, 15, 9, 15),
            'pickup_window_minutes': 10,
            'dropoff_window_minutes': 10,
            'has_arrival_constraint': True,
            'is_tight_constraint': True,
            'available_trip_time_minutes': 45,
            'actual_trip_duration_minutes': 40,
            'estimated_duration_minutes': 40,
            'passenger_count': 1,
            'request_time': datetime(2025, 1, 15, 8, 30),
        }

        print("\n--- Example: Morning Commute with Tight Deadline ---")
        result = llm_gen.generate(trip_data)
        print(f"Request: \"{result['request']}\"")
        print(f"Model: {result.get('model', 'unknown')}")
        print()

        # Airport example
        trip_data_airport = {
            'pickup_zone': 'Manhattan',
            'dropoff_zone': 'JFK Airport',
            'dropoff_poi': 'JFK Airport',
            'requested_pickup_time': datetime(2025, 1, 15, 13, 0),
            'requested_dropoff_time': datetime(2025, 1, 15, 15, 30),
            'pickup_window_minutes': 15,
            'dropoff_window_minutes': 15,
            'has_arrival_constraint': True,
            'is_tight_constraint': False,
            'available_trip_time_minutes': 150,
            'actual_trip_duration_minutes': 120,
            'estimated_duration_minutes': 120,
            'passenger_count': 2,
            'request_time': datetime(2025, 1, 15, 13, 0),
        }

        print("--- Example: Airport Trip with Flight Deadline ---")
        result = llm_gen.generate(trip_data_airport)
        print(f"Request: \"{result['request']}\"")
        print()

    except Exception as e:
        print(f"LLM generation not available: {e}")
        print("(Make sure OPENAI_API_KEY or ANTHROPIC_API_KEY is set)")
        print()


def demo_statistics():
    """Demo showing statistics about time windows."""

    print("="*80)
    print("DEMO: Time Window Statistics")
    print("="*80)
    print()

    # Simulate generating time windows for 100 trips
    print("Simulating time window generation for 100 trips...")
    print()

    trips = []
    for i in range(100):
        # Simulate real trip data
        is_rush_hour = random.random() < 0.3
        has_arrival = random.random() < 0.6

        trip = {
            'id': i,
            'is_rush_hour': is_rush_hour,
            'has_arrival_constraint': has_arrival,
            'pickup_window_minutes': random.randint(5, 10) if is_rush_hour else random.randint(10, 20),
        }

        if has_arrival:
            trip['dropoff_window_minutes'] = random.randint(5, 15)
            trip['actual_duration'] = random.randint(20, 120)
            trip['available_time'] = trip['actual_duration'] + random.randint(-20, 40)
            trip['is_tight_constraint'] = trip['available_time'] < trip['actual_duration'] + 10
        else:
            trip['dropoff_window_minutes'] = None
            trip['is_tight_constraint'] = False

        trips.append(trip)

    # Calculate statistics
    total = len(trips)
    with_arrival = sum(1 for t in trips if t['has_arrival_constraint'])
    tight = sum(1 for t in trips if t['is_tight_constraint'])

    avg_pickup_window = sum(t['pickup_window_minutes'] for t in trips) / total
    avg_dropoff_window = sum(t['dropoff_window_minutes'] for t in trips if t['dropoff_window_minutes']) / with_arrival if with_arrival > 0 else 0

    print(f"Total trips: {total}")
    print(f"With arrival constraints: {with_arrival} ({with_arrival/total*100:.1f}%)")
    print(f"With tight constraints: {tight} ({tight/total*100:.1f}%)")
    print()
    print(f"Average pickup window: {avg_pickup_window:.1f} minutes")
    print(f"Average dropoff window: {avg_dropoff_window:.1f} minutes (when present)")
    print()

    # Show breakdown by rush hour
    rush_hour_trips = [t for t in trips if t['is_rush_hour']]
    normal_trips = [t for t in trips if not t['is_rush_hour']]

    if rush_hour_trips:
        avg_rush = sum(t['pickup_window_minutes'] for t in rush_hour_trips) / len(rush_hour_trips)
        print(f"Rush hour avg pickup window: {avg_rush:.1f} minutes")

    if normal_trips:
        avg_normal = sum(t['pickup_window_minutes'] for t in normal_trips) / len(normal_trips)
        print(f"Normal hours avg pickup window: {avg_normal:.1f} minutes")

    print()


def demo_comparison():
    """Demo comparing requests with and without time constraints."""

    print("="*80)
    print("DEMO: Comparing Requests With/Without Time Constraints")
    print("="*80)
    print()

    generator = TemplateGenerator()

    base_trip = {
        'pickup_zone': 'Times Square',
        'dropoff_zone': 'JFK Airport',
        'dropoff_poi': 'JFK',
        'requested_pickup_time': datetime(2025, 1, 15, 14, 0),
        'pickup_window_minutes': 10,
        'request_time': datetime(2025, 1, 15, 14, 0),
        'estimated_duration_minutes': 90,
    }

    # Without arrival constraint
    print("--- WITHOUT Arrival Constraint ---")
    trip_no_constraint = {**base_trip}
    result = generator.generate(trip_no_constraint, tier='basic')
    print(f"Request: \"{result['request']}\"")
    print("Type: Flexible pickup, no arrival deadline")
    print()

    # With arrival constraint (loose)
    print("--- WITH Arrival Constraint (Loose) ---")
    trip_loose = {
        **base_trip,
        'requested_dropoff_time': datetime(2025, 1, 15, 16, 30),
        'dropoff_window_minutes': 15,
        'has_arrival_constraint': True,
        'is_tight_constraint': False,
        'available_trip_time_minutes': 150,
        'actual_trip_duration_minutes': 90,
    }
    result = generator.generate(trip_loose, tier='time_constrained')
    print(f"Request: \"{result['request']}\"")
    print(f"Type: Must arrive by {trip_loose['requested_dropoff_time'].strftime('%I:%M %p')}")
    print(f"Margin: {trip_loose['available_trip_time_minutes'] - trip_loose['actual_trip_duration_minutes']:.0f} minutes buffer")
    print()

    # With arrival constraint (tight)
    print("--- WITH Arrival Constraint (TIGHT) ---")
    trip_tight = {
        **base_trip,
        'requested_dropoff_time': datetime(2025, 1, 15, 15, 35),
        'dropoff_window_minutes': 5,
        'has_arrival_constraint': True,
        'is_tight_constraint': True,
        'available_trip_time_minutes': 95,
        'actual_trip_duration_minutes': 90,
    }
    result = generator.generate(trip_tight, tier='time_constrained')
    print(f"Request: \"{result['request']}\"")
    print(f"Type: URGENT - must arrive by {trip_tight['requested_dropoff_time'].strftime('%I:%M %p')}")
    print(f"Margin: Only {trip_tight['available_trip_time_minutes'] - trip_tight['actual_trip_duration_minutes']:.0f} minutes buffer!")
    print()


def main():
    """Run all demos."""

    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "TIME WINDOWS & ARRIVAL CONSTRAINTS DEMO" + " "*19 + "║")
    print("╚" + "="*78 + "╝")
    print("\n")

    demo_template_generation()
    print("\n")

    demo_llm_generation()
    print("\n")

    demo_statistics()
    print("\n")

    demo_comparison()
    print("\n")

    print("="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print("\nKey Takeaways:")
    print("  • 60% of requests have arrival time constraints")
    print("  • ~15-20% have tight constraints (urgent)")
    print("  • Pickup windows: 5-20 minutes (tighter in rush hour)")
    print("  • Dropoff windows: 5-15 minutes (when constrained)")
    print("  • Natural language automatically incorporates time info")
    print("\nFor more info, see: src/request_simulation/TIME_WINDOWS_GUIDE.md")
    print()


if __name__ == "__main__":
    main()
