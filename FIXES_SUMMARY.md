# Simulation Timing and Event Processing Fixes

## Summary of Issues and Fixes

This document describes the critical timing issues found in the vehicle simulation system and the fixes applied.

---

## Issue #1: Time Snapping in VehicleSimulator.advance_time()

### Problem
In `src/vehicle_system/vehicle_simulator.py`, the `advance_time()` method was snapping all event timestamps to the end of the time jump (`new_time`), rather than using the actual scheduled event times.

**Consequences:**
- Pickup events that should occur at `estimated_pickup_time` were recorded as happening at `new_time`
- Dropoff times were anchored to `new_time` instead of the actual pickup time
- In long time jumps, many events would collapse to the same timestamp
- Trajectory visualizations showed unrealistic clustering of events

### Fix
**File:** `src/vehicle_system/vehicle_simulator.py` (lines 179-220)

**Changes:**
1. Store `actual_pickup_time = trip_info['estimated_pickup_time']` instead of using `new_time`
2. Update vehicle location at `actual_pickup_time` instead of `new_time`
3. Calculate `estimated_dropoff_time` from `actual_pickup_time` instead of `new_time`
4. Use `actual_dropoff_time = trip_info.get('estimated_dropoff_time')` for completions

**Before:**
```python
vehicle.update_location(trip_info['pickup_location'], new_time)
trip_info['actual_pickup_time_timestamp'] = new_time
trip_info['estimated_dropoff_time'] = new_time + timedelta(minutes=trip_time)
```

**After:**
```python
actual_pickup_time = trip_info['estimated_pickup_time']
vehicle.update_location(trip_info['pickup_location'], actual_pickup_time)
trip_info['actual_pickup_time_timestamp'] = actual_pickup_time
trip_info['estimated_dropoff_time'] = actual_pickup_time + timedelta(minutes=trip_time)
```

---

## Issue #2: Missing Pickup Time Metric in Trip Results

### Problem
The evaluator at `src/evaluation/evaluator.py` (line 272) reads `trip_result.get('actual_pickup_time', 0.0)`, expecting a float in minutes. However, the simulator only stored `actual_pickup_time_timestamp` (a datetime), not the duration in minutes. This caused pickup time metrics to always be 0.0.

### Fix
**File:** `src/vehicle_system/vehicle_simulator.py` (lines 169-186)

**Changes:**
Added calculation of `actual_pickup_time` in minutes when completing a trip:

```python
# Calculate actual pickup time in minutes for evaluator
# This is the time between request and actual pickup
if 'actual_pickup_time_timestamp' in trip_info and 'request_time' in trip_info:
    pickup_time_delta = trip_info['actual_pickup_time_timestamp'] - trip_info['request_time']
    trip_info['actual_pickup_time'] = pickup_time_delta.total_seconds() / 60.0
else:
    trip_info['actual_pickup_time'] = trip_info.get('actual_pickup_time_minutes', 0.0)
```

Now the evaluator correctly receives pickup times in minutes and can compute accurate average pickup time metrics.

---

## Issue #3: Request-Only Time Advancement (No Event-Driven Scheduling)

### Problem
In `src/environment/green_agent_environment.py`, time only advanced at:
1. Each request arrival (line 259)
2. One final jump to `simulation_end_time` (line 359)

There was no scheduler to advance time at exact vehicle event times (pickups/dropoffs). This meant:
- Long gaps between requests would cause large time jumps
- All vehicle events in the gap would be processed in one batch
- Events would be timestamped at the end of the jump (due to Issue #1)
- Trajectories showed unrealistic temporal clustering

### Fix
**File:** `src/environment/green_agent_environment.py`

**Changes:**

1. **New method: `_advance_to_time_with_events()`** (lines 691-738)
   - Implements event-driven simulation
   - Collects upcoming vehicle events between current time and target time
   - Advances time incrementally to each event
   - Processes events at their exact scheduled times

2. **New method: `_get_next_vehicle_event_time()`** (lines 740-758)
   - Scans all active trips for next pickup or dropoff event
   - Returns the earliest event time
   - Returns None if no pending events

3. **Updated call sites:**
   - Line 259: Changed `self._advance_to_time(nl_request.request_time)` to `self._advance_to_time_with_events(nl_request.request_time)`
   - Line 359: Changed `self._advance_to_time(self.simulation_end_time)` to `self._advance_to_time_with_events(self.simulation_end_time)`

**Algorithm:**
```python
def _advance_to_time_with_events(self, target_time):
    while current_time < target_time:
        next_event_time = _get_next_vehicle_event_time()
        
        if next_event_time is None or next_event_time >= target_time:
            # No events before target, advance directly
            _advance_to_time(target_time)
            break
        
        # Advance to next event time
        _advance_to_time(next_event_time)
```

This ensures that vehicle events (pickups and dropoffs) are processed at their exact scheduled times, producing accurate trajectories and timestamps.

---

## Issue #4: Dual Pickup Time Estimates (Documentation)

### Problem
Two different "estimated pickup times" exist in the system:
1. **Agent's estimate:** `routing_decision.estimated_pickup_time` (from white agent)
2. **Simulator's estimate:** `trip_info['estimated_pickup_time']` (calculated by simulator)

These can disagree, which can confuse debugging and analysis.

### Fix
**Files:** 
- `src/vehicle_system/vehicle_simulator.py` (lines 54-73)
- `src/environment/green_agent_environment.py` (line 299)

**Changes:**
Added clear documentation explaining:
- The agent's estimate is a prediction made by the white agent
- The simulator's estimate is ground truth based on actual distance calculation
- The simulator's estimate is used for actual trip execution
- Both are logged for comparison and debugging

**Documentation added to `execute_routing_decision()`:**
```python
"""
Note on dual pickup time estimates:
- The routing_decision contains the agent's estimated_pickup_time (agent's prediction)
- This method calculates the simulator's estimated_pickup_time (ground truth based on actual distance)
- The simulator's estimate is used for actual trip execution
- Both are logged for comparison and debugging purposes
"""
```

---

## Issue #5: Fallback Pickup Time Assignment Bug (Edge Case Fix)

### Problem
In `src/vehicle_system/vehicle_simulator.py` (line 189), the fallback for pickup time calculation used:
```python
trip_info['actual_pickup_time'] = trip_info.get('actual_pickup_time_minutes', 0.0)
```

The key `'actual_pickup_time_minutes'` doesn't exist. If forced completion happens before pickup is processed, this would incorrectly overwrite any existing `'actual_pickup_time'` with 0.0.

### Fix
**File:** `src/vehicle_system/vehicle_simulator.py` (lines 183-190)

**Changes:**
Changed fallback to preserve existing values:

**Before:**
```python
else:
    trip_info['actual_pickup_time'] = trip_info.get('actual_pickup_time_minutes', 0.0)
```

**After:**
```python
elif 'actual_pickup_time' not in trip_info:
    # Only set to 0.0 if no pickup time exists at all (preserve existing value)
    trip_info['actual_pickup_time'] = 0.0
```

Now the fallback only sets 0.0 if no pickup time exists, preserving any existing value.

---

## Issue #6: Infinite Loop Guard in Event Scheduler (Edge Case Fix)

### Problem
In `src/environment/green_agent_environment.py` (line 717), the event scheduler could loop forever if `_get_next_vehicle_event_time()` ever returns a time <= `self.current_time`. This would happen because:
1. Loop condition: `while self.current_time < target_time`
2. Call `_advance_to_time(next_event_time)` where `next_event_time <= current_time`
3. `_advance_to_time()` early-returns without advancing time
4. Loop repeats infinitely

While rare, this could occur due to floating-point precision issues, clock adjustments, or bugs in event time calculation.

### Fix
**File:** `src/environment/green_agent_environment.py` (lines 717-737)

**Changes:**
Added guard to detect and handle past event times:

```python
# Guard against infinite loop: skip events in the past or at current time
if next_event_time <= self.current_time:
    # This shouldn't happen, but if it does, log error and advance to target
    self.logger.log_error(
        error_type='INVALID_EVENT_TIME',
        error_message=f'Next event time {next_event_time} is not after current time {self.current_time}',
        context={'next_event_time': next_event_time.isoformat(), 'current_time': self.current_time.isoformat()}
    )
    self._advance_to_time(target_time)
    break
```

Now if an invalid event time is detected:
1. Error is logged with full context for debugging
2. Simulation advances directly to target time
3. Loop terminates, preventing infinite loop

---

## Impact and Benefits

### Before Fixes:
- ❌ Events collapsed to same timestamps in visualizations
- ❌ Pickup time metrics always showed 0.0
- ❌ Large time jumps between requests caused batch event processing
- ❌ Trajectories showed unrealistic temporal clustering
- ❌ Difficult to debug timing issues

### After Fixes:
- ✅ Events occur at exact scheduled times
- ✅ Pickup time metrics accurately reflect actual wait times
- ✅ Event-driven simulation processes events incrementally
- ✅ Trajectories show realistic temporal distribution
- ✅ Clear documentation of dual estimates for debugging

---

## Testing Recommendations

To verify the fixes work correctly:

1. **Run baseline evaluation:**
   ```bash
   python3 examples/evaluate_baselines.py
   ```

2. **Check trajectory visualization:**
   - Open generated `trajectories_map.html`
   - Verify pickups and dropoffs are temporally distributed (not clustered)
   - Check that events don't all occur at the same timestamps

3. **Verify pickup time metrics:**
   - Check evaluation summary for non-zero average pickup times
   - Confirm pickup times are realistic (e.g., 5-15 minutes)

4. **Inspect event log:**
   - Check `events.json` for accurate timestamps
   - Verify `actual_pickup_time_timestamp` differs from request arrival times
   - Confirm dropoff times are spaced appropriately after pickups

---

## Files Modified

1. `src/vehicle_system/vehicle_simulator.py`
   - Fixed time snapping in `advance_time()` (Issue #1)
   - Added pickup time calculation in `simulate_trip_completion()` (Issue #2)
   - Fixed fallback pickup time assignment (Issue #5)
   - Added documentation for dual estimates (Issue #4)

2. `src/environment/green_agent_environment.py`
   - Added `_advance_to_time_with_events()` method (Issue #3)
   - Added `_get_next_vehicle_event_time()` method (Issue #3)
   - Added infinite loop guard (Issue #6)
   - Updated call sites to use event-driven advancement (Issue #3)
   - Added documentation comments (Issue #4)

3. `FIXES_SUMMARY.md` (this file)
   - Comprehensive documentation of all issues and fixes

4. `verify_fixes.py`
   - Automated verification script for all fixes

---

## Notes

- The original `_advance_to_time()` method is preserved and used internally by `_advance_to_time_with_events()`
- The fixes are backward compatible - no API changes to external interfaces
- Performance impact is minimal - event scheduling adds O(n) scan per time advancement where n is number of active trips
- For large fleets, consider optimizing `_get_next_vehicle_event_time()` with a priority queue if needed

