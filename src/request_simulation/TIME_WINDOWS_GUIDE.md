# Time Windows & Arrival Constraints Guide

## Overview

The request simulation module now supports realistic time windows and arrival constraints, making the generated ride requests much more realistic. Instead of just a pickup request time, the system now generates:

1. **Pickup time windows** - Flexibility around when the customer can be picked up
2. **Arrival time constraints** - When the customer needs to arrive at their destination
3. **Tight vs. loose constraints** - Urgency indicators based on available time

## Key Features

### 1. Time Window Generation

Based on actual trip data (request_datetime, pickup_datetime, dropoff_datetime), the system generates:

**Pickup Times:**
- `requested_pickup_time`: When the customer wants to be picked up (= request_datetime)
- `pickup_window_minutes`: Flexibility around pickup (5-20 minutes)
  - Rush hour: 5-10 minutes (tighter)
  - Normal hours: 10-20 minutes (more flexible)

**Arrival Times (60% of requests):**
- `requested_dropoff_time`: When the customer needs to arrive
  - Calculated from actual dropoff_datetime ± 15 minutes
- `dropoff_window_minutes`: Flexibility around arrival (5-15 minutes)
- `has_arrival_constraint`: Boolean flag

**Time Pressure:**
- `available_trip_time_minutes`: Time between requested pickup and requested arrival
- `actual_trip_duration_minutes`: How long the trip actually took
- `is_tight_constraint`: True if available time < actual time + 10 min buffer

### 2. Natural Language Integration

The time windows are automatically incorporated into generated requests:

**Template Examples:**

```
Basic:
"I need a taxi from Times Square to JFK at 3:30 PM"
"I need a taxi from Times Square to JFK at 3:30 PM (can be ready in 15 minutes)"
"I need a taxi from Times Square to JFK at 3:30 PM, need to arrive by 5:00 PM"

Time-Constrained:
"I need to arrive at JFK Airport by 5:00 PM for my flight"
"I need to arrive at JFK Airport by 5:00 PM (±10 minutes) for my flight"
"It's urgent - I need to arrive at JFK Airport by 5:00 PM for my flight"
"I'm running late - I have to be at JFK by 5:00 PM, give or take 10 minutes"

Complex:
"Wheelchair-accessible from Times Square to JFK, 2 passengers, arrive by 5 PM"
```

**LLM Examples:**

The LLM receives structured information about time constraints and generates natural variations:

```
"Hey, I need a ride from my place in the Upper West Side to my office in Brooklyn Heights.
Can you pick me up at 8:30 AM? I need to be there by 9 AM - I have a meeting. Thanks!"

"I'm at Times Square and need to get to JFK Airport. It's urgent - my flight is at 5 PM
and I need to be there by 4:30 PM at the latest. Can you send a car ASAP?"
```

## Data Flow

### 1. Data Preprocessing

```python
from src.request_simulation import NYCTripDataPreprocessor

preprocessor = NYCTripDataPreprocessor("taxi_zone_lookup.csv")
df = preprocessor.preprocess_pipeline("trip_data.parquet", sample_size=10000)

# Now df contains:
# - requested_pickup_time
# - requested_dropoff_time (for 60% of requests)
# - pickup_window_minutes
# - dropoff_window_minutes
# - has_arrival_constraint
# - is_tight_constraint
# - available_trip_time_minutes
```

### 2. Request Generation

The time window fields are automatically used by template and LLM generators:

```python
from src.request_simulation import TemplateGenerator

generator = TemplateGenerator()

trip_data = {
    'pickup_zone': 'Times Square',
    'dropoff_zone': 'JFK Airport',
    'requested_pickup_time': datetime(2025, 1, 15, 14, 30),
    'requested_dropoff_time': datetime(2025, 1, 15, 16, 0),
    'pickup_window_minutes': 10,
    'dropoff_window_minutes': 10,
    'has_arrival_constraint': True,
    'is_tight_constraint': True,
    'available_trip_time_minutes': 85,
    'actual_trip_duration_minutes': 75
}

result = generator.generate(trip_data, tier='time_constrained')
print(result['request'])
# "It's urgent - I need to arrive at JFK Airport by 4:00 PM (±10 minutes) for my flight"
```

## Configuration

### Adjust Probability of Arrival Constraints

Edit `src/request_simulation/data_preprocessing.py`:

```python
# Line ~172: Change from 0.6 (60%) to desired value
df_time['has_arrival_constraint'] = df_time.apply(
    lambda _: random.random() < 0.8,  # 80% have arrival constraints
    axis=1
)
```

### Adjust Time Window Sizes

Edit the window generation logic:

```python
# Pickup windows
df_time['pickup_window_minutes'] = df_time.apply(
    lambda row: random.randint(3, 7) if row.get('is_rush_hour', False)  # Tighter
    else random.randint(5, 15),  # Looser
    axis=1
)

# Dropoff windows
df_time['dropoff_window_minutes'] = df_time.apply(
    lambda row: random.randint(3, 10) if row['has_arrival_constraint']  # Tighter
    else None,
    axis=1
)
```

### Adjust Tight Constraint Definition

```python
# Line ~215: Change buffer from 10 to desired value
df_time['is_tight_constraint'] = df_time.apply(
    lambda row: row['has_arrival_constraint'] and
    row['available_trip_time_minutes'] is not None and
    row['available_trip_time_minutes'] < (row['actual_trip_duration_minutes'] + 5),  # Tighter: 5 min
    axis=1
)
```

## Output Format

The generated request JSON now includes time window fields:

```json
{
  "trip_id": 123,
  "request": "It's urgent - I need to arrive at JFK Airport by 5:00 PM for my flight",
  "generation_method": "template",
  "tier": "time_constrained",

  "pickup_zone": "Times Square",
  "dropoff_zone": "JFK Airport",

  "requested_pickup_time": "2025-01-15T14:30:00",
  "requested_dropoff_time": "2025-01-15T17:00:00",

  "pickup_window_minutes": 10,
  "dropoff_window_minutes": 10,

  "has_arrival_constraint": true,
  "is_tight_constraint": true,

  "available_trip_time_minutes": 150,
  "actual_trip_duration_minutes": 145,

  "trip_miles": 16.5,
  "estimated_duration_minutes": 145
}
```

## Statistics

After preprocessing, you can check the statistics:

```python
df = preprocessor.preprocess_pipeline("data.parquet", sample_size=10000)

# Print statistics
print(f"Total requests: {len(df)}")
print(f"With arrival constraints: {df['has_arrival_constraint'].sum()} ({df['has_arrival_constraint'].mean()*100:.1f}%)")
print(f"With tight constraints: {df['is_tight_constraint'].sum()} ({df['is_tight_constraint'].mean()*100:.1f}%)")
print(f"\nAverage pickup window: {df['pickup_window_minutes'].mean():.1f} minutes")
print(f"Average dropoff window: {df['dropoff_window_minutes'].mean():.1f} minutes (when present)")
```

Example output:
```
Total requests: 10000
With arrival constraints: 6012 (60.1%)
With tight constraints: 1523 (15.2%)

Average pickup window: 14.8 minutes
Average dropoff window: 9.7 minutes (when present)
```

## Use Cases

### 1. Airport Trips

Arrival constraints are especially realistic for airport trips:

```
"I need to be at JFK Airport by 4:30 PM for my 6 PM flight"
"Pick me up from Times Square, I have to catch my 5 PM flight at LaGuardia"
```

### 2. Business Meetings

Time-constrained requests for meetings:

```
"I need to arrive at Financial District by 9 AM for a meeting"
"It's urgent - I have a 10 AM presentation at Midtown, need to leave now"
```

### 3. Rush Hour

Tighter windows during rush hour:

```
"I need a ride from Brooklyn to Manhattan at 8:30 AM (can be ready in 5 minutes)"
```

### 4. Flexible Requests

Loose constraints for non-urgent trips:

```
"I need a taxi from my place to the Upper East Side, anytime around 2 PM (±20 minutes is fine)"
```

## Integration with Routing Algorithms

The time window data can be used by routing algorithms for:

1. **Feasibility Checking**: Is there enough time to complete the trip?
2. **Priority Assignment**: Tight constraints get higher priority
3. **Route Optimization**: Balance time constraints with efficiency
4. **Customer Satisfaction**: Meeting arrival times improves ratings

Example:
```python
# Check if trip is feasible
available_time = request['available_trip_time_minutes']
estimated_time = request['estimated_duration_minutes']

if available_time and available_time < estimated_time:
    print("WARNING: Tight constraint - may not be feasible!")

# Assign priority
if request['is_tight_constraint']:
    priority = "HIGH"
elif request['has_arrival_constraint']:
    priority = "MEDIUM"
else:
    priority = "LOW"
```

## Example: Complete Pipeline

```python
from src.request_simulation import RequestSimulator

# Initialize simulator
simulator = RequestSimulator(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    template_ratio=0.5
)

# Load and preprocess with time windows
df = simulator.load_and_preprocess_data(
    "trip_data.parquet",
    sample_size=1000
)

# Check time window statistics
print(f"Arrival constraints: {df['has_arrival_constraint'].mean()*100:.1f}%")
print(f"Tight constraints: {df['is_tight_constraint'].mean()*100:.1f}%")

# Generate profiles
simulator.customer_db.generate_profiles(200)

# Simulate requests (time windows automatically included)
requests = simulator.simulate_requests(
    df,
    n_requests=100,
    save_output="output/requests_with_timewindows.json"
)

# Analyze time constraints
time_constrained = [r for r in requests if r.get('has_arrival_constraint')]
tight_constrained = [r for r in requests if r.get('is_tight_constraint')]

print(f"\nGenerated {len(requests)} requests:")
print(f"  With arrival time: {len(time_constrained)} ({len(time_constrained)/len(requests)*100:.1f}%)")
print(f"  With tight constraint: {len(tight_constrained)} ({len(tight_constrained)/len(requests)*100:.1f}%)")

# Print examples
print("\n--- Example Time-Constrained Requests ---")
for req in time_constrained[:5]:
    print(f"\nRequest: \"{req['request']}\"")
    print(f"  Pickup: {req['requested_pickup_time']}")
    print(f"  Arrival: {req['requested_dropoff_time']}")
    print(f"  Available: {req['available_trip_time_minutes']:.0f} min")
    print(f"  Needed: {req['actual_trip_duration_minutes']:.0f} min")
    print(f"  Tight: {req['is_tight_constraint']}")
```

## Debugging

### Check Time Window Generation

```python
# After preprocessing, inspect a single trip
trip = df.iloc[0]

print("Time Window Analysis:")
print(f"Request time: {trip['request_datetime']}")
print(f"Requested pickup: {trip['requested_pickup_time']}")
print(f"Pickup window: ±{trip['pickup_window_minutes']} min")

if trip['has_arrival_constraint']:
    print(f"\nArrival constraint: YES")
    print(f"Requested arrival: {trip['requested_dropoff_time']}")
    print(f"Dropoff window: ±{trip['dropoff_window_minutes']} min")
    print(f"Available time: {trip['available_trip_time_minutes']:.0f} min")
    print(f"Actual duration: {trip['actual_trip_duration_minutes']:.0f} min")
    print(f"Tight constraint: {trip['is_tight_constraint']}")
else:
    print(f"\nArrival constraint: NO")
```

### Validate Time Windows

```python
# Check for invalid time windows
invalid = df[
    (df['has_arrival_constraint']) &
    (df['requested_dropoff_time'] < df['requested_pickup_time'])
]

if len(invalid) > 0:
    print(f"WARNING: Found {len(invalid)} trips with arrival before pickup!")
```

## Best Practices

1. **Always preprocess data** to generate time windows before simulation
2. **Check statistics** to ensure realistic distribution of constraints
3. **Use time_constrained tier** for requests with arrival constraints
4. **Set appropriate window sizes** based on use case (airport vs. local)
5. **Monitor tight constraints** - too many may indicate unrealistic data

## Future Enhancements

- [ ] Support for multi-stop time windows
- [ ] Dynamic window sizing based on traffic conditions
- [ ] Customer preference learning (some always tight, some always loose)
- [ ] Seasonal/event-based constraint adjustments
- [ ] Integration with real-time ETA predictions

## Troubleshooting

**Issue**: All requests have the same window size

**Solution**: Check that randomization is working in generate_time_windows()

**Issue**: No arrival constraints generated

**Solution**: Verify dropoff_datetime exists in your data and probability is set correctly

**Issue**: Too many tight constraints

**Solution**: Adjust the buffer in is_tight_constraint calculation (increase from 10 to 15-20 minutes)

**Issue**: Arrival time before pickup time

**Solution**: Check arrival_buffer_minutes calculation - may need to adjust range

## Support

For questions or issues:
- Check this guide first
- Review data preprocessing output
- Examine a few sample requests to verify time windows
- See main README: `src/request_simulation/README.md`
