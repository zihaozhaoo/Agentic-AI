# Location Augmentation - Enhanced with Smart Sampling & Detailed Logging

## Overview

The location augmentation module has been significantly enhanced with:

1. **Detailed Logging**: Comprehensive logging at every step for easy debugging
2. **Smart Sampling**: Intelligent location selection to better match expected trip distances
3. **Statistics Tracking**: Monitor API usage, cache performance, and errors

## Key Features

### 1. Smart Sampling Algorithm

Instead of using just the zone center, the smart sampling algorithm:

1. **Samples Multiple Origins**: Generates 3 (configurable) candidate pickup locations per zone
   - First candidate: Geocoded zone center
   - Additional candidates: Random points within the zone bounds

2. **Samples Multiple Destinations**: Generates 3 (configurable) candidate dropoff locations per zone
   - First candidate: Geocoded zone center
   - Additional candidates: Random points within the zone bounds

3. **Tests All Combinations**: Tests up to 9 (3×3) origin-destination pairs

4. **Selects Best Match**: Chooses the pair that minimizes distance error
   - Stops early if a match within tolerance is found
   - Logs each trial for debugging

### 2. Detailed Logging

All operations are logged with different levels:

- **INFO**: Main operations, results, statistics
- **DEBUG**: Detailed step-by-step operations
- **WARNING**: Fallbacks and edge cases
- **ERROR**: Failures and exceptions

#### Log Output Example

```
2025-10-19 15:30:45 - location_augmentation - INFO - ================================================================================
2025-10-19 15:30:45 - location_augmentation - INFO - Augmenting trip: Times Sq/Theatre District (ID 230) -> JFK Airport (ID 132)
2025-10-19 15:30:45 - location_augmentation - INFO - Expected distance: 16.50 miles
2025-10-19 15:30:45 - location_augmentation - INFO - Using SMART SAMPLING with 3 origin × 3 dest candidates
2025-10-19 15:30:45 - location_augmentation - INFO - Searching for best location pair among 3 origins and 3 destinations
2025-10-19 15:30:45 - location_augmentation - INFO - Target distance: 16.50 miles (tolerance: 30%)
2025-10-19 15:30:45 - location_augmentation - DEBUG - Testing pair 1,1: origin (40.7589, -73.9851) -> dest (40.6413, -73.7781)
2025-10-19 15:30:46 - location_augmentation - DEBUG - API result: 26.50 km, 45.2 min
2025-10-19 15:30:46 - location_augmentation - DEBUG - Result: 16.46 miles, error: 0.2%
2025-10-19 15:30:46 - location_augmentation - INFO - ✓ New best pair found! Distance: 16.46 miles, error: 0.2%
2025-10-19 15:30:46 - location_augmentation - INFO - ✓ Found acceptable match within tolerance!
2025-10-19 15:30:46 - location_augmentation - INFO - Best pair selected: origin zone 230 -> dest zone 132
2025-10-19 15:30:46 - location_augmentation - INFO - Distance: 16.46 miles, Duration: 45.2 min
2025-10-19 15:30:46 - location_augmentation - INFO - Expected: 16.50 miles, Error: 0.2%
2025-10-19 15:30:46 - location_augmentation - INFO - Within tolerance: True
```

### 3. Statistics Tracking

The module tracks:
- Total API calls
- Cache hits/misses
- Cache hit rate
- Geocoding failures
- Direction API failures
- Number of cached zones and locations

## Usage

### Basic Usage

```python
from src.request_simulation import LocationAugmenter

# Initialize with smart sampling (default: 3×3 candidates)
augmenter = LocationAugmenter(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    num_origin_samples=3,
    num_dest_samples=3
)

# Augment a single trip with smart sampling
result = augmenter.augment_trip(
    pickup_zone_id=230,  # Times Square
    dropoff_zone_id=132,  # JFK Airport
    pickup_zone_name="Times Sq/Theatre District",
    dropoff_zone_name="JFK Airport",
    expected_distance_miles=16.5,
    use_smart_sampling=True  # Default
)

# Print statistics
augmenter.print_statistics()
```

### Configuration Options

```python
# More aggressive sampling (5×5 = 25 trials max)
augmenter = LocationAugmenter(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    num_origin_samples=5,
    num_dest_samples=5
)

# Conservative sampling (2×2 = 4 trials max)
augmenter = LocationAugmenter(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    num_origin_samples=2,
    num_dest_samples=2
)
```

### Comparing Smart vs Simple Sampling

```python
# Smart sampling
smart_result = augmenter.augment_trip(
    ...,
    use_smart_sampling=True
)

# Simple sampling (zone centers only)
simple_result = augmenter.augment_trip(
    ...,
    use_smart_sampling=False
)

print(f"Smart: {smart_result['distance_error_pct']:.1f}% error")
print(f"Simple: {simple_result['distance_error_pct']:.1f}% error")
```

### Batch Processing

```python
# Process multiple trips
augmented_df = augmenter.augment_dataframe(
    df,
    max_samples=100,
    rate_limit_delay=0.1,
    use_smart_sampling=True
)

# Check statistics after batch
augmenter.print_statistics()
```

## Output Format

The augmented trip result includes:

```python
{
    'pickup_location': {
        'zone_id': 230,
        'zone_name': 'Times Sq/Theatre District',
        'latitude': 40.7589,
        'longitude': -73.9851,
        'address': '1500 Broadway, New York, NY 10036'
    },
    'dropoff_location': {
        'zone_id': 132,
        'zone_name': 'JFK Airport',
        'latitude': 40.6413,
        'longitude': -73.7781,
        'address': 'John F Kennedy International Airport, Queens, NY'
    },
    'estimated_distance_km': 26.50,
    'estimated_distance_miles': 16.46,
    'estimated_duration_minutes': 45.2,
    'expected_distance_miles': 16.50,
    'is_distance_valid': True,
    'distance_error_pct': 0.24,
    'num_trials': 1,  # Stopped early - found match within tolerance
    'sampling_method': 'smart'
}
```

## Logging Configuration

### Change Log Level

```python
import logging

# Set to DEBUG for detailed logs
logging.getLogger('location_augmentation').setLevel(logging.DEBUG)

# Set to INFO for main operations only
logging.getLogger('location_augmentation').setLevel(logging.INFO)

# Set to WARNING to suppress most logs
logging.getLogger('location_augmentation').setLevel(logging.WARNING)
```

### Log to File

```python
import logging

# Create file handler
file_handler = logging.FileHandler('location_augmentation.log')
file_handler.setLevel(logging.DEBUG)

# Add formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)

# Add handler to logger
logger = logging.getLogger('location_augmentation')
logger.addHandler(file_handler)
```

## Configuration in YAML

Update `configs/request_simulation.yaml`:

```yaml
location_augmentation:
  enabled: true
  use_cache: true
  use_smart_sampling: true  # Enable smart sampling
  num_origin_samples: 3     # Number of origin candidates
  num_dest_samples: 3       # Number of destination candidates
  rate_limit_delay: 0.1
  distance_tolerance: 0.3   # 30% acceptable error
```

## Performance Considerations

### API Calls

**Simple Sampling (zone centers only):**
- 2 API calls per trip (1 geocode origin + 1 geocode dest + 1 directions)
- Fast but less accurate

**Smart Sampling (3×3 candidates):**
- Up to 11 API calls per trip in worst case:
  - 2 geocode calls (zone centers)
  - 4 random point generations (no API)
  - Up to 9 directions API calls (tests each pair)
- Stops early if match found within tolerance
- Much more accurate distance matching

### Caching Benefits

With caching enabled:
- First trip: 11 API calls (3×3 smart sampling)
- Second trip (same zones): 0 API calls (all cached)
- Cache hit rate > 90% for typical datasets

Example from 100 trips:
```
Total API calls: 250
Cache hits: 450
Cache misses: 50
Cache hit rate: 90.0%
```

## Debugging Tips

### 1. Check Logs

Look for these patterns in logs:

**Problem**: High distance errors
```
Distance Error: 45.2% (valid: False)
```
**Solution**: Enable smart sampling or increase num_samples

**Problem**: Too many API calls
```
Total API calls: 5000
```
**Solution**: Enable caching, reduce num_samples

**Problem**: Geocoding failures
```
Geocoding FAILED for zone 264 (Unknown): ...
```
**Solution**: Check zone lookup table, verify API key

### 2. Statistics Output

After running augmentation, always check:

```python
augmenter.print_statistics()
```

Look for:
- High failure rates → Check API key, network
- Low cache hit rate → Increase sample size for better caching
- High API calls → Reduce num_samples or enable caching

### 3. Individual Trip Debugging

Set log level to DEBUG and run a single trip:

```python
logging.getLogger('location_augmentation').setLevel(logging.DEBUG)

result = augmenter.augment_trip(...)
```

You'll see every API call, every candidate tested, and why decisions were made.

## Examples

### Example 1: Test Smart Sampling

```bash
# Run the demo
python src/request_simulation/location_augmentation.py
```

This will:
1. Test smart sampling (3×3) on Times Square → JFK
2. Test simple sampling on the same trip
3. Compare results
4. Print statistics

### Example 2: Batch Augmentation

```python
from src.request_simulation import LocationAugmenter, NYCTripDataPreprocessor

# Load data
preprocessor = NYCTripDataPreprocessor("taxi_zone_lookup.csv")
df = preprocessor.preprocess_pipeline("data.parquet", sample_size=100)

# Augment
augmenter = LocationAugmenter(
    "taxi_zone_lookup.csv",
    num_origin_samples=3,
    num_dest_samples=3
)

augmented_df = augmenter.augment_dataframe(
    df,
    use_smart_sampling=True
)

# Statistics
augmenter.print_statistics()

# Save cache for reuse
augmenter.save_cache("data/cache/location_cache.json")
```

### Example 3: Load and Reuse Cache

```python
# First run
augmenter1 = LocationAugmenter("taxi_zone_lookup.csv")
# ... do work ...
augmenter1.save_cache("location_cache.json")

# Later run
augmenter2 = LocationAugmenter("taxi_zone_lookup.csv")
augmenter2.load_cache("location_cache.json")
# Now all previously seen zones are cached!
```

## Troubleshooting

### Issue: "Too many requests" error from Google Maps API

**Cause**: Hitting API rate limits

**Solutions**:
1. Increase `rate_limit_delay` (e.g., to 0.5 seconds)
2. Reduce `num_origin_samples` and `num_dest_samples`
3. Use caching aggressively
4. Process in smaller batches

### Issue: Poor distance matching even with smart sampling

**Cause**: Zones are too large or irregular

**Solutions**:
1. Increase `num_origin_samples` and `num_dest_samples` (e.g., to 5)
2. Relax `distance_tolerance` (e.g., to 0.5 for 50%)
3. Use finer-grained zone data if available

### Issue: Logs too verbose

**Cause**: DEBUG level logging

**Solution**:
```python
import logging
logging.getLogger('location_augmentation').setLevel(logging.INFO)
```

### Issue: No logs appearing

**Cause**: Logging not configured

**Solution**:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Best Practices

1. **Always enable caching** for production use
2. **Start with 3×3 sampling** and adjust based on results
3. **Monitor API usage** with print_statistics()
4. **Save cache** after batch processing for reuse
5. **Use DEBUG logs** during development, INFO in production
6. **Set appropriate rate_limit_delay** (0.1s minimum)
7. **Test on small sample** before processing large datasets

## API Cost Estimation

Assuming $0.005 per Google Maps API call:

| Configuration | Calls/Trip | Cost/Trip | Cost/1000 Trips |
|--------------|------------|-----------|-----------------|
| Simple (no cache) | 3 | $0.015 | $15.00 |
| Smart 3×3 (no cache) | ~11 | $0.055 | $55.00 |
| Smart 3×3 (90% cache) | ~1.1 | $0.0055 | $5.50 |

**Recommendation**: Always use caching for production!

## Future Enhancements

- [ ] Support for custom zone boundaries (polygons)
- [ ] Multi-threaded batch processing
- [ ] Progressive sampling (start with 2×2, increase if needed)
- [ ] Machine learning-based location prediction
- [ ] Integration with real-time traffic data

## Support

For issues or questions:
1. Check logs with DEBUG level
2. Run `print_statistics()` to diagnose
3. Review this guide
4. Check the main module README: `src/request_simulation/README.md`
