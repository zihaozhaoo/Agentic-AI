# Request Simulation Examples

This directory contains examples and tutorials for using the Request Simulation module.

## Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set up API keys** (choose one or both for LLM generation):

For OpenAI:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

For Anthropic:
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

For Google Maps (optional, for location augmentation):
```bash
export GOOGLE_MAPS_API_KEY="your-google-maps-api-key"
```

3. **Download NYC taxi data** (if not already available):
```bash
# Download from NYC TLC website
wget https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2025-01.parquet
```

## Running the Example

### Basic Usage

```bash
python examples/simulate_requests.py
```

This will:
1. Load and preprocess 10,000 trip records
2. Generate 500 customer profiles
3. Create 1,000 natural language requests (50% template, 50% LLM)
4. Save results to `data/output/simulated_requests.json`

### Custom Configuration

Edit `configs/request_simulation.yaml` to customize:

```yaml
# Change number of requests
simulation:
  n_requests: 5000

# Use only templates (no LLM)
nl_generation:
  template_ratio: 1.0

# Enable location augmentation
location_augmentation:
  enabled: true
```

## Step-by-Step Tutorial

### 1. Data Preprocessing Only

```python
from src.request_simulation import NYCTripDataPreprocessor

preprocessor = NYCTripDataPreprocessor("taxi_zone_lookup.csv")

# Load and clean data
df = preprocessor.preprocess_pipeline(
    "../fhvhv_tripdata_2025-01.parquet",
    sample_size=10000,
    save_dir="data/processed"
)

# Create benchmark splits
splits = preprocessor.sample_for_benchmark(
    df,
    dev_size=5000,
    val_size=2500,
    test_size=2500
)

print(f"Dev: {len(splits['dev'])} trips")
print(f"Val: {len(splits['val'])} trips")
print(f"Test: {len(splits['test'])} trips")
```

### 2. POI Database Creation

```python
from src.request_simulation import POIDatabase

poi_db = POIDatabase("taxi_zone_lookup.csv")

# View statistics
stats = poi_db.get_statistics()
print(f"Total POIs: {stats['total_pois']}")
print(f"Categories: {stats['categories']}")

# Get specific POIs
airports = poi_db.get_pois_by_category("airport")
for airport in airports:
    print(f"- {airport.name} in {airport.borough}")

# Save for later use
poi_db.save_to_json("data/poi/poi_database.json")
```

### 3. Customer Profile Generation

```python
from src.request_simulation import CustomerProfileDatabase

customer_db = CustomerProfileDatabase("taxi_zone_lookup.csv")

# Generate profiles
customer_db.generate_profiles(1000)

# View a sample profile
profile = customer_db.get_random_profile()
print(f"Customer: {profile.customer_id}")
print(f"Home: {profile.home.zone_name} ({profile.home.borough})")
if profile.work:
    print(f"Work: {profile.work.zone_name} ({profile.work.borough})")

# Save profiles
customer_db.save_to_json("data/customers/customer_profiles.json")
```

### 4. Template-Based Generation

```python
from src.request_simulation import TemplateGenerator
from datetime import datetime

generator = TemplateGenerator()

trip_data = {
    'pickup_zone': 'Times Square',
    'dropoff_zone': 'JFK Airport',
    'pickup_poi': 'Times Square',
    'dropoff_poi': 'JFK',
    'request_time': datetime(2025, 1, 15, 14, 30),
    'estimated_duration_minutes': 45,
    'passenger_count': 2
}

# Generate each tier
for tier in ['basic', 'poi_based', 'time_constrained', 'multi_stop', 'complex']:
    result = generator.generate(trip_data, tier=tier)
    print(f"\n{tier.upper()}:")
    print(f"  {result['request']}")

# Generate random tier
result = generator.generate(trip_data)
print(f"\n{result['tier'].upper()}:")
print(f"  {result['request']}")
```

### 5. LLM-Based Generation

```python
from src.request_simulation import LLMGenerator
from datetime import datetime

# Using OpenAI
openai_gen = LLMGenerator(provider="openai")

trip_data = {
    'pickup_zone': 'Upper West Side',
    'dropoff_zone': 'Brooklyn Heights',
    'pickup_personal': 'home',
    'dropoff_personal': 'work',
    'request_time': datetime(2025, 1, 15, 8, 30),
    'passenger_count': 1
}

result = openai_gen.generate(trip_data)
print(f"OpenAI: {result['request']}")

# Using Anthropic
anthropic_gen = LLMGenerator(provider="anthropic")
result = anthropic_gen.generate(trip_data)
print(f"Anthropic: {result['request']}")
```

### 6. Complete Simulation Pipeline

```python
from src.request_simulation import RequestSimulator

# Initialize
simulator = RequestSimulator(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    llm_provider="openai",
    template_ratio=0.5
)

# Load data
df = simulator.load_and_preprocess_data(
    "../fhvhv_tripdata_2025-01.parquet",
    sample_size=10000
)

# Generate profiles
simulator.customer_db.generate_profiles(500)

# Simulate requests
requests = simulator.simulate_requests(
    df,
    n_requests=1000,
    augment_location=False,  # Set True to use Google Maps
    save_output="data/output/requests.json"
)

# Get statistics
stats = simulator.get_statistics(requests)
print(f"Total: {stats['total_requests']}")
print(f"Methods: {stats['generation_methods']}")
```

## Advanced Usage

### Custom Template Tiers

```python
from src.request_simulation import TemplateGenerator

# Modify tier probabilities
generator = TemplateGenerator()
generator.tier_probabilities = {
    'basic': 0.50,
    'poi_based': 0.30,
    'time_constrained': 0.10,
    'multi_stop': 0.05,
    'complex': 0.05
}
```

### Batch Processing with Rate Limiting

```python
from src.request_simulation import LLMGenerator

generator = LLMGenerator(provider="openai")

# Process multiple trips
trip_data_list = [...]  # List of trip dictionaries

results = generator.generate_batch(
    trip_data_list,
    rate_limit_delay=0.5  # 0.5 seconds between calls
)
```

### Using Cached Locations

```python
from src.request_simulation import LocationAugmenter

augmenter = LocationAugmenter(
    "taxi_zone_lookup.csv",
    use_cache=True
)

# First run: calls API
trip1 = augmenter.augment_trip(230, 132, "Times Square", "JFK")

# Save cache
augmenter.save_cache("data/cache/location_cache.json")

# Later: load cache
augmenter2 = LocationAugmenter("taxi_zone_lookup.csv")
augmenter2.load_cache("data/cache/location_cache.json")

# Second run: uses cache, no API call
trip2 = augmenter2.augment_trip(230, 132, "Times Square", "JFK")
```

## Output Examples

### Template-Based Request
```json
{
  "tier": "basic",
  "request": "I need a taxi from Times Square to JFK Airport at 2:30 PM",
  "generation_method": "template",
  "pickup_zone": "Times Sq/Theatre District",
  "dropoff_zone": "JFK Airport",
  "request_time": "2025-01-15T14:30:00"
}
```

### LLM-Based Request
```json
{
  "request": "Hey, can I get picked up from my place on the Upper West Side? I need to get to my office in Brooklyn Heights by 9 AM. Thanks!",
  "generation_method": "llm_openai",
  "model": "gpt-4o-mini",
  "pickup_zone": "Upper West Side South",
  "dropoff_zone": "Brooklyn Heights",
  "pickup_personal": "home",
  "dropoff_personal": "work"
}
```

## Troubleshooting

### Issue: LLM API errors

**Solution**: Check API keys are set correctly
```bash
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
```

### Issue: Google Maps API quota exceeded

**Solution**: Enable caching and reduce augmentation
```python
simulator = RequestSimulator(
    use_location_cache=True
)

requests = simulator.simulate_requests(
    df,
    augment_location=False  # Disable to avoid API calls
)
```

### Issue: Out of memory

**Solution**: Reduce sample size
```python
df = simulator.load_and_preprocess_data(
    parquet_file,
    sample_size=1000  # Start small
)
```

## Next Steps

1. Integrate with White Agent for parsing evaluation
2. Connect to routing solver for dispatch testing
3. Implement streaming simulation for online testing
4. Add visualization of generated requests on a map

## Support

For issues or questions, refer to:
- Module documentation: `src/request_simulation/README.md`
- Project proposal: `Proposal.md`
- Main README: `README.md`
