# Request Simulation Module

This module provides a comprehensive framework for simulating realistic ride-hailing requests from structured NYC taxi trip data.

## Overview

The Request Simulation module converts structured trip records into natural language ride requests that can be used to evaluate AI agents for ride-hailing dispatch. It follows the design specified in the project proposal, implementing:

1. **Data Preprocessing**: Clean and enrich NYC TLC HVFHV trip data
2. **Location Augmentation**: Generate exact coordinates using Google Maps API
3. **POI Database**: Manage points of interest for natural language references
4. **Customer Profiles**: Generate synthetic customer profiles with personal locations
5. **Natural Language Generation**: Create requests using templates (50%) and LLMs (50%)

## Architecture

```
request_simulation/
├── __init__.py                  # Module exports
├── data_preprocessing.py        # NYC trip data cleaning and preprocessing
├── poi_database.py              # Points of Interest database
├── customer_profiles.py         # Synthetic customer profile generation
├── location_augmentation.py     # Google Maps API integration
├── template_generator.py        # Template-based NL generation
├── llm_generator.py             # LLM-based NL generation (OpenAI/Anthropic)
└── request_simulator.py         # Main orchestrator
```

## Quick Start

### Installation

```bash
# Install required packages
pip install pandas numpy googlemaps openai anthropic pyyaml
```

### Basic Usage

```python
from src.request_simulation import RequestSimulator

# Initialize simulator
simulator = RequestSimulator(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    llm_provider="openai",  # or "anthropic"
    template_ratio=0.5  # 50% template, 50% LLM
)

# Load and preprocess data
df = simulator.load_and_preprocess_data(
    "fhvhv_tripdata_2025-01.parquet",
    sample_size=10000
)

# Generate customer profiles
simulator.customer_db.generate_profiles(500)

# Simulate requests
requests = simulator.simulate_requests(
    df,
    n_requests=1000,
    save_output="output/simulated_requests.json"
)
```

### Using the Example Script

```bash
# Edit configuration
nano configs/request_simulation.yaml

# Set API keys
export OPENAI_API_KEY="your-key-here"
# or
export ANTHROPIC_API_KEY="your-key-here"

# Run simulation
python examples/simulate_requests.py
```

## Module Components

### 1. Data Preprocessing (`data_preprocessing.py`)

Loads and cleans NYC TLC HVFHV trip data:
- Removes invalid location IDs and trip data
- Enriches with zone information (borough, zone names)
- Extracts temporal features (hour, day of week, rush hour flags)
- Splits data into dev/val/test sets

**Example:**
```python
from src.request_simulation import NYCTripDataPreprocessor

preprocessor = NYCTripDataPreprocessor("taxi_zone_lookup.csv")
df = preprocessor.preprocess_pipeline(
    "fhvhv_tripdata_2025-01.parquet",
    sample_size=10000
)
```

### 2. POI Database (`poi_database.py`)

Manages points of interest for natural language references:
- Airports: JFK, LaGuardia, Newark
- Transit hubs: Penn Station, Grand Central
- Landmarks: Times Square, Empire State Building, Central Park
- Business districts: Wall Street, World Trade Center
- Neighborhoods: SoHo, Williamsburg, Chinatown

**Example:**
```python
from src.request_simulation import POIDatabase

poi_db = POIDatabase("taxi_zone_lookup.csv")
jfk = poi_db.get_poi_by_name("JFK Airport")
airports = poi_db.get_pois_by_category("airport")
```

### 3. Customer Profiles (`customer_profiles.py`)

Generates synthetic customer profiles with personal locations:
- Home location
- Work location (80% of customers)
- 1-3 frequent locations (gym, favorite restaurant, etc.)

**Example:**
```python
from src.request_simulation import CustomerProfileDatabase

customer_db = CustomerProfileDatabase("taxi_zone_lookup.csv")
customer_db.generate_profiles(500)

# Assign profile to a trip
profile = customer_db.assign_profile_to_trip(
    pickup_zone=230,  # Times Square
    dropoff_zone=132  # JFK
)
```

### 4. Location Augmentation (`location_augmentation.py`)

Augments trips with exact coordinates using Google Maps API:
- Geocodes taxi zones to get approximate centers
- Calculates actual driving distances and durations
- Validates against expected trip distances
- Caches results to minimize API calls

**Example:**
```python
from src.request_simulation import LocationAugmenter

augmenter = LocationAugmenter("taxi_zone_lookup.csv")

augmented = augmenter.augment_trip(
    pickup_zone_id=230,
    dropoff_zone_id=132,
    pickup_zone_name="Times Square",
    dropoff_zone_name="JFK Airport",
    expected_distance_miles=16.5
)
```

### 5. Template Generator (`template_generator.py`)

Generates natural language requests using five template tiers:

1. **Basic** (30%): Simple origin-destination-time
   - "I need a taxi from Times Square to JFK Airport at 3:30 PM"

2. **POI-based** (25%): Using points of interest
   - "Pick me up at Grand Central and take me to the Empire State Building"

3. **Time-constrained** (20%): Arrival time requirements
   - "I need to arrive at LaGuardia by 5 PM for my flight"

4. **Multi-stop** (10%): Multiple destinations
   - "Pick me up at Penn Station, stop at Brooklyn, then to JFK"

5. **Complex** (15%): Accessibility, passengers, luggage
   - "Wheelchair-accessible vehicle from 57th St to JFK, 2 passengers, 3 bags"

**Example:**
```python
from src.request_simulation import TemplateGenerator

generator = TemplateGenerator()

trip_data = {
    'pickup_zone': 'Upper East Side',
    'dropoff_zone': 'JFK Airport',
    'pickup_poi': 'Central Park',
    'request_time': datetime.now(),
    'passenger_count': 2
}

result = generator.generate(trip_data, tier='basic')
print(result['request'])
```

### 6. LLM Generator (`llm_generator.py`)

Generates natural language requests using LLMs (OpenAI or Anthropic):
- More varied and natural phrasing
- Contextual awareness (time of day, rush hour)
- Configurable temperature for creativity

**Example:**
```python
from src.request_simulation import LLMGenerator

generator = LLMGenerator(provider="openai")
result = generator.generate(trip_data)
print(result['request'])
```

### 7. Request Simulator (`request_simulator.py`)

Main orchestrator that combines all components:
- Loads and preprocesses data
- Augments with POIs and customer profiles
- Generates NL requests (50/50 template/LLM by default)
- Saves results in JSON or Parquet format

## Configuration

Edit `configs/request_simulation.yaml` to customize:

```yaml
# Generation mix
nl_generation:
  template_ratio: 0.5  # 50% template, 50% LLM

# Template tier probabilities
template_tiers:
  basic: 0.30
  poi_based: 0.25
  time_constrained: 0.20
  multi_stop: 0.10
  complex: 0.15

# Location augmentation (Google Maps API)
location_augmentation:
  enabled: false  # Set to true to use API (expensive)
  use_cache: true
```

## Output Format

Generated requests are saved as JSON with the following structure:

```json
{
  "trip_id": 123,
  "request": "I need a ride from Central Park to JFK Airport at 2:30 PM",
  "generation_method": "template",
  "tier": "basic",
  "pickup_zone": "Upper East Side",
  "dropoff_zone": "JFK Airport",
  "pickup_zone_id": 237,
  "dropoff_zone_id": 132,
  "request_time": "2025-01-15T14:30:00",
  "estimated_duration_minutes": 45,
  "passenger_count": 2,
  "customer_id": "CUST_000042"
}
```

## API Requirements

### Google Maps API (Optional)
- Enable Geocoding API and Directions API
- Set `GOOGLE_MAPS_API_KEY` environment variable
- Note: Can be expensive for large datasets, use caching

### OpenAI API (Optional)
- Set `OPENAI_API_KEY` environment variable
- Default model: `gpt-4o-mini` (faster and cheaper)

### Anthropic API (Optional)
- Set `ANTHROPIC_API_KEY` environment variable
- Default model: `claude-3-haiku-20240307` (faster and cheaper)

## Performance Considerations

- **Location augmentation**: Disable for large-scale simulations (use zone-level data)
- **LLM generation**: Use caching and rate limiting to avoid API costs
- **Batch processing**: Process requests in batches with appropriate delays
- **Caching**: Enable caching for locations and geocoding results

## Testing Individual Modules

Each module can be tested independently:

```bash
# Test data preprocessing
python src/request_simulation/data_preprocessing.py

# Test POI database
python src/request_simulation/poi_database.py

# Test customer profiles
python src/request_simulation/customer_profiles.py

# Test location augmentation
python src/request_simulation/location_augmentation.py

# Test template generator
python src/request_simulation/template_generator.py

# Test LLM generator
python src/request_simulation/llm_generator.py

# Test complete simulator
python src/request_simulation/request_simulator.py
```

## Integration with Green Agent

This module is part of the Green Agent evaluation framework. The generated requests can be:

1. Fed to White Agents for parsing and dispatch
2. Used to evaluate parsing accuracy
3. Combined with routing algorithms for end-to-end testing
4. Analyzed for realism and diversity

## Future Enhancements

- [ ] Add more NYC-specific POIs
- [ ] Implement more sophisticated customer behavior patterns
- [ ] Add support for real-time traffic conditions
- [ ] Generate multi-passenger/ride-sharing requests
- [ ] Add support for international locations
- [ ] Implement request streaming for online simulation

## License

Part of the CS294 Agentic AI Green Agent project.
