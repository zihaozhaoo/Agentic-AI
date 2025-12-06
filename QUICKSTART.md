# Quick Start Guide - Request Simulation Module

Get up and running with the Request Simulation module in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- NYC taxi trip data (Parquet file)
- API keys for OpenAI or Anthropic (optional, but recommended)

## Installation

```bash
# Clone or navigate to the project
cd Agentic-AI

# Install dependencies
pip install -r requirements.txt
```

## Set Up API Keys

Choose one LLM provider (or both):

```bash
# For OpenAI (recommended: gpt-4o-mini)
export OPENAI_API_KEY="your-openai-api-key"

# OR for Anthropic (recommended: claude-3-haiku)
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Optional: For location augmentation
export GOOGLE_MAPS_API_KEY="your-google-maps-api-key"
```

## Quick Run

### Option 1: Use the Example Script (Recommended)

```bash
# Run with default configuration
python examples/simulate_requests.py
```

This will:
- Load 10,000 trip records
- Generate 500 customer profiles
- Create 1,000 natural language requests
- Save to `data/output/simulated_requests.json`

### Option 2: Python Code

```python
from src.request_simulation import RequestSimulator

# Initialize
simulator = RequestSimulator(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    llm_provider="openai",  # or "anthropic"
    template_ratio=0.5      # 50% template, 50% LLM
)

# Load data
df = simulator.load_and_preprocess_data(
    "../fhvhv_tripdata_2025-01.parquet",
    sample_size=1000
)

# Generate profiles
simulator.customer_db.generate_profiles(100)

# Simulate requests
requests = simulator.simulate_requests(
    df,
    n_requests=100,
    save_output="output/requests.json"
)

# Print example
print(requests[0]['request'])
```

## Configuration

Edit `configs/request_simulation.yaml`:

```yaml
# Adjust generation mix
nl_generation:
  template_ratio: 0.5  # 0.0 = all LLM, 1.0 = all template

# Change request count
simulation:
  n_requests: 1000

# Disable expensive location augmentation
location_augmentation:
  enabled: false
```

## Output

Generated requests look like this:

```json
{
  "request": "I need a taxi from Times Square to JFK Airport at 3:30 PM",
  "tier": "basic",
  "generation_method": "template",
  "pickup_zone": "Times Sq/Theatre District",
  "dropoff_zone": "JFK Airport",
  "pickup_zone_id": 230,
  "dropoff_zone_id": 132,
  "request_time": "2025-01-15T15:30:00",
  "trip_miles": 16.5
}
```

## Next Steps

1. **Customize templates**: Edit template probabilities in config
2. **Add more POIs**: Modify `src/request_simulation/poi_database.py`
3. **Adjust customer behavior**: Tune `customer_profiles.py`
4. **Enable location augmentation**: Set `location_augmentation.enabled: true` (requires Google Maps API)
5. **Integrate with routing**: Connect to your dispatch algorithm

## Troubleshooting

### No LLM API key?
Set `template_ratio: 1.0` to use only templates (no API needed)

### Out of memory?
Reduce `sample_size` and `n_requests` in config

### API rate limits?
Increase `llm_rate_limit_delay` in config

## Learn More

- Full documentation: `src/request_simulation/README.md`
- Examples: `examples/README.md`
- Project proposal: `Proposal.md`

## Support

For issues, check the documentation or review the proposal for design details.

---

**Happy simulating!** 🚕
