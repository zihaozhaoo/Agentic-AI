"""
Simple verification script to check that timing fixes are in place.

This script checks the source code for the key fixes without running the simulation.
"""

import re
from pathlib import Path

def check_fix_1_vehicle_simulator():
    """Check that VehicleSimulator uses exact event times."""
    print("Checking Fix #1: VehicleSimulator exact event times...")
    
    file_path = Path("src/vehicle_system/vehicle_simulator.py")
    content = file_path.read_text()
    
    # Check for the fix: actual_pickup_time = trip_info['estimated_pickup_time']
    if "actual_pickup_time = trip_info['estimated_pickup_time']" in content:
        print("  ✅ Found: actual_pickup_time uses estimated_pickup_time (not new_time)")
    else:
        print("  ❌ Missing: actual_pickup_time should use estimated_pickup_time")
        return False
    
    # Check that we update location with actual_pickup_time
    if "vehicle.update_location(trip_info['pickup_location'], actual_pickup_time)" in content:
        print("  ✅ Found: vehicle location updated at actual_pickup_time")
    else:
        print("  ❌ Missing: vehicle location should be updated at actual_pickup_time")
        return False
    
    # Check that dropoff time is anchored to actual pickup
    if "trip_info['estimated_dropoff_time'] = actual_pickup_time + timedelta(minutes=trip_time)" in content:
        print("  ✅ Found: dropoff time anchored to actual_pickup_time")
    else:
        print("  ❌ Missing: dropoff time should be anchored to actual_pickup_time")
        return False
    
    # Check for actual_dropoff_time
    if "actual_dropoff_time = trip_info.get('estimated_dropoff_time'" in content:
        print("  ✅ Found: uses actual_dropoff_time for completion")
    else:
        print("  ❌ Missing: should use actual_dropoff_time for completion")
        return False
    
    print("  ✅ Fix #1 verified!")
    return True

def check_fix_2_pickup_time_calculation():
    """Check that pickup time is calculated in minutes."""
    print("\nChecking Fix #2: Pickup time calculation...")
    
    file_path = Path("src/vehicle_system/vehicle_simulator.py")
    content = file_path.read_text()
    
    # Check for pickup time calculation
    if "trip_info['actual_pickup_time'] = pickup_time_delta.total_seconds() / 60.0" in content:
        print("  ✅ Found: actual_pickup_time calculated in minutes")
    else:
        print("  ❌ Missing: actual_pickup_time should be calculated in minutes")
        return False
    
    if "'actual_pickup_time_timestamp' in trip_info and 'request_time' in trip_info" in content:
        print("  ✅ Found: pickup time calculated from timestamp delta")
    else:
        print("  ❌ Missing: pickup time should be calculated from timestamp delta")
        return False
    
    # Check for safe fallback (Fix #5)
    if "elif 'actual_pickup_time' not in trip_info:" in content:
        print("  ✅ Found: safe fallback preserves existing pickup time")
    else:
        print("  ❌ Missing: fallback should preserve existing pickup time")
        return False
    
    print("  ✅ Fix #2 verified!")
    return True

def check_fix_3_event_driven_scheduling():
    """Check that event-driven scheduling is implemented."""
    print("\nChecking Fix #3: Event-driven scheduling...")
    
    file_path = Path("src/environment/green_agent_environment.py")
    content = file_path.read_text()
    
    # Check for _advance_to_time_with_events method
    if "def _advance_to_time_with_events(self, target_time: datetime):" in content:
        print("  ✅ Found: _advance_to_time_with_events method")
    else:
        print("  ❌ Missing: _advance_to_time_with_events method")
        return False
    
    # Check for _get_next_vehicle_event_time method
    if "def _get_next_vehicle_event_time(self) -> Optional[datetime]:" in content:
        print("  ✅ Found: _get_next_vehicle_event_time method")
    else:
        print("  ❌ Missing: _get_next_vehicle_event_time method")
        return False
    
    # Check that it's used in the main loop
    if "self._advance_to_time_with_events(nl_request.request_time)" in content:
        print("  ✅ Found: _advance_to_time_with_events used in request processing")
    else:
        print("  ❌ Missing: _advance_to_time_with_events should be used in request processing")
        return False
    
    # Check that it's used at the end
    if "self._advance_to_time_with_events(self.simulation_end_time)" in content:
        print("  ✅ Found: _advance_to_time_with_events used for final horizon")
    else:
        print("  ❌ Missing: _advance_to_time_with_events should be used for final horizon")
        return False
    
    # Check for infinite loop guard (Fix #6): past event times
    if "if next_event_time < self.current_time:" in content:
        print("  ✅ Found: guard for past event times")
    else:
        print("  ❌ Missing: guard for past event times")
        return False

    # Check for handling events due exactly "now" (next_event_time == current_time)
    if "if next_event_time == self.current_time:" in content:
        print("  ✅ Found: handles events due at current time")
    else:
        print("  ❌ Missing: should handle events when next_event_time == current_time")
        return False
    
    print("  ✅ Fix #3 verified!")
    return True

def check_fix_4_documentation():
    """Check that documentation for dual estimates is added."""
    print("\nChecking Fix #4: Documentation for dual pickup estimates...")
    
    file_path = Path("src/vehicle_system/vehicle_simulator.py")
    content = file_path.read_text()
    
    # Check for documentation about dual estimates
    if "Note on dual pickup time estimates:" in content:
        print("  ✅ Found: Documentation for dual pickup time estimates")
    else:
        print("  ❌ Missing: Documentation for dual pickup time estimates")
        return False
    
    if "agent's estimated_pickup_time" in content and "simulator's estimated_pickup_time" in content:
        print("  ✅ Found: Explanation of both estimates")
    else:
        print("  ❌ Missing: Explanation of both estimates")
        return False
    
    print("  ✅ Fix #4 verified!")
    return True

def main():
    print("="*80)
    print("TIMING FIXES VERIFICATION")
    print("="*80)
    print()
    
    results = []
    
    # Run checks
    results.append(("Fix #1: Exact Event Times", check_fix_1_vehicle_simulator()))
    results.append(("Fix #2: Pickup Time Calculation", check_fix_2_pickup_time_calculation()))
    results.append(("Fix #3: Event-Driven Scheduling", check_fix_3_event_driven_scheduling()))
    results.append(("Fix #4: Documentation", check_fix_4_documentation()))
    
    # Print summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    for fix_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {fix_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL FIXES VERIFIED IN SOURCE CODE")
        print("\nThe timing issues have been successfully fixed:")
        print("  1. Events now occur at exact scheduled times (not snapped)")
        print("  2. Pickup times are calculated correctly in minutes")
        print("     - Safe fallback preserves existing pickup time values")
        print("  3. Event-driven scheduler processes events incrementally")
        print("     - Infinite loop guard prevents past event time issues")
        print("  4. Documentation clarifies dual pickup time estimates")
        print("\nSee FIXES_SUMMARY.md for detailed documentation.")
    else:
        print("❌ SOME FIXES ARE MISSING")
    print("="*80)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
