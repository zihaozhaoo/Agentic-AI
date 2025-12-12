"""
Location Augmentation Module

This module augments trip data with exact coordinates by sampling random points
within taxi zones and validating them against trip distances using Google Maps API.
"""

import pandas as pd
import numpy as np
try:
    import googlemaps
    GOOGLEMAPS_AVAILABLE = True
except ImportError:
    googlemaps = None
    GOOGLEMAPS_AVAILABLE = False
from typing import Dict, List, Tuple, Optional
import time
import random
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict

from .zone_coordinates import get_zone_coordinate, get_borough_bounds, BOROUGH_LAND_BOUNDS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ExactLocation:
    """Exact location with coordinates."""
    zone_id: int
    zone_name: str
    latitude: float
    longitude: float
    address: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class LocationAugmenter:
    """Augments trip data with exact coordinates."""

    def __init__(
        self,
        taxi_zone_lookup_path: str,
        google_maps_api_key: Optional[str] = None,
        use_cache: bool = True,
        num_origin_samples: int = 3,
        num_dest_samples: int = 3
    ):
        """
        Initialize location augmenter.

        Args:
            taxi_zone_lookup_path: Path to taxi zone lookup CSV
            google_maps_api_key: Google Maps API key (if None, reads from existing gmap.py)
            use_cache: Whether to cache geocoding results
            num_origin_samples: Number of origin candidates to sample per zone
            num_dest_samples: Number of destination candidates to sample per zone
        """
        logger.info(f"Initializing LocationAugmenter with taxi zone lookup: {taxi_zone_lookup_path}")
        self.zone_lookup = pd.read_csv(taxi_zone_lookup_path)
        logger.info(f"Loaded {len(self.zone_lookup)} taxi zones")

        # Initialize Google Maps client
        if google_maps_api_key is None:
            # Use the API key from existing gmap.py
            google_maps_api_key = "AIzaSyASdmnEivZx-7u6s8tRQn4UbPZ8E9SDe8Y"
            logger.warning("Using hardcoded Google Maps API key - consider using environment variable")

        if GOOGLEMAPS_AVAILABLE:
            self.gmaps = googlemaps.Client(key=google_maps_api_key)
            logger.info("Google Maps client initialized")
        else:
            self.gmaps = None
            logger.warning("Google Maps client NOT initialized (module not found)")

        # Cache for geocoded locations
        self.location_cache: Dict[int, List[ExactLocation]] = {}
        self.use_cache = use_cache
        self.num_origin_samples = num_origin_samples
        self.num_dest_samples = num_dest_samples

        logger.info(f"Configuration: use_cache={use_cache}, origin_samples={num_origin_samples}, dest_samples={num_dest_samples}")

        # Statistics tracking
        self.stats = {
            'total_api_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'geocoding_failures': 0,
            'direction_failures': 0
        }

    def _generate_random_point_in_zone(self, zone_id: int) -> Tuple[float, float]:
        """
        Generate a random lat/lon point within a taxi zone's approximate bounds.
        
        Uses zone-specific centroids when available, otherwise samples from
        land-only borough bounds to prevent points falling in water.

        Args:
            zone_id: Taxi zone ID

        Returns:
            Tuple of (latitude, longitude) guaranteed to be on land
        """
        zone_info = self.zone_lookup[self.zone_lookup['LocationID'] == zone_id]
        if zone_info.empty:
            logger.warning(f"Zone {zone_id} not found in lookup, using NYC center")
            # Default to Times Square area (safe Manhattan location)
            return (40.7580 + random.uniform(-0.002, 0.002), 
                    -73.9855 + random.uniform(-0.002, 0.002))

        borough = zone_info.iloc[0]['Borough']
        zone_name = zone_info.iloc[0]['Zone']
        
        # Use centralized zone coordinate lookup with moderate jitter for sampling
        lat, lon = get_zone_coordinate(zone_id, borough, jitter=0.003)

        logger.debug(f"Generated random point for zone {zone_id} ({zone_name}, {borough}): ({lat:.4f}, {lon:.4f})")
        return (lat, lon)

    def geocode_zone(self, zone_id: int, zone_name: str) -> ExactLocation:
        """
        Geocode a taxi zone to get an approximate center point.

        Args:
            zone_id: Taxi zone ID
            zone_name: Zone name

        Returns:
            ExactLocation object
        """
        # Check cache first
        if self.use_cache and zone_id in self.location_cache:
            self.stats['cache_hits'] += 1
            cached_loc = random.choice(self.location_cache[zone_id])
            logger.debug(f"Cache HIT for zone {zone_id} ({zone_name}): ({cached_loc.latitude:.4f}, {cached_loc.longitude:.4f})")
            return cached_loc

        self.stats['cache_misses'] += 1
        logger.debug(f"Cache MISS for zone {zone_id} ({zone_name}), geocoding...")

        # Try geocoding the zone name
        try:
            self.stats['total_api_calls'] += 1
            geocode_result = self.gmaps.geocode(f"{zone_name}, New York, NY")

            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                address = geocode_result[0].get('formatted_address', None)

                exact_loc = ExactLocation(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    latitude=location['lat'],
                    longitude=location['lng'],
                    address=address
                )

                logger.info(f"Geocoded zone {zone_id} ({zone_name}): ({exact_loc.latitude:.4f}, {exact_loc.longitude:.4f})")

                # Cache the result
                if self.use_cache:
                    if zone_id not in self.location_cache:
                        self.location_cache[zone_id] = []
                    self.location_cache[zone_id].append(exact_loc)

                return exact_loc

        except Exception as e:
            self.stats['geocoding_failures'] += 1
            logger.error(f"Geocoding FAILED for zone {zone_id} ({zone_name}): {e}")

        # Fallback: generate random point
        logger.warning(f"Using random fallback point for zone {zone_id} ({zone_name})")
        lat, lon = self._generate_random_point_in_zone(zone_id)

        return ExactLocation(
            zone_id=zone_id,
            zone_name=zone_name,
            latitude=lat,
            longitude=lon
        )

    def get_distance_and_duration(
        self,
        origin: ExactLocation,
        destination: ExactLocation
    ) -> Tuple[float, float]:
        """
        Get driving distance and duration between two locations using Google Maps.

        Args:
            origin: Origin location
            destination: Destination location

        Returns:
            Tuple of (distance_km, duration_minutes)
        """
        logger.debug(f"Getting directions from zone {origin.zone_id} to zone {destination.zone_id}")

        try:
            self.stats['total_api_calls'] += 1
            directions = self.gmaps.directions(
                origin=(origin.latitude, origin.longitude),
                destination=(destination.latitude, destination.longitude),
                mode="driving"
            )

            if directions:
                leg = directions[0]['legs'][0]
                distance_km = leg['distance']['value'] / 1000.0  # meters to km
                duration_min = leg['duration']['value'] / 60.0  # seconds to minutes

                logger.debug(f"API result: {distance_km:.2f} km, {duration_min:.1f} min")
                return (distance_km, duration_min)

        except Exception as e:
            self.stats['direction_failures'] += 1
            logger.error(f"Directions API FAILED: {e}")

        # Fallback: use haversine distance
        logger.warning(f"Using haversine fallback for distance calculation")
        distance_km = self._haversine_distance(origin, destination)
        # Assume average speed of 20 km/h in NYC
        duration_min = (distance_km / 20.0) * 60

        logger.debug(f"Haversine result: {distance_km:.2f} km, {duration_min:.1f} min")
        return (distance_km, duration_min)

    def _haversine_distance(self, loc1: ExactLocation, loc2: ExactLocation) -> float:
        """
        Calculate haversine distance between two locations in km.

        Args:
            loc1: First location
            loc2: Second location

        Returns:
            Distance in kilometers
        """
        from math import radians, sin, cos, sqrt, atan2

        R = 6371  # Earth radius in km

        lat1, lon1 = radians(loc1.latitude), radians(loc1.longitude)
        lat2, lon2 = radians(loc2.latitude), radians(loc2.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    def _generate_location_candidates(
        self,
        zone_id: int,
        zone_name: str,
        num_candidates: int
    ) -> List[ExactLocation]:
        """
        Generate multiple candidate locations within a zone.

        Args:
            zone_id: Taxi zone ID
            zone_name: Zone name
            num_candidates: Number of candidates to generate

        Returns:
            List of ExactLocation candidates
        """
        logger.debug(f"Generating {num_candidates} location candidates for zone {zone_id} ({zone_name})")

        candidates = []

        # First candidate: use geocoded center (from cache or API)
        center_loc = self.geocode_zone(zone_id, zone_name)
        candidates.append(center_loc)

        # Additional candidates: random points within the zone
        for i in range(num_candidates - 1):
            lat, lon = self._generate_random_point_in_zone(zone_id)
            random_loc = ExactLocation(
                zone_id=zone_id,
                zone_name=zone_name,
                latitude=lat,
                longitude=lon
            )
            candidates.append(random_loc)
            logger.debug(f"  Candidate {i+2}/{num_candidates}: ({lat:.4f}, {lon:.4f})")

        return candidates

    def _find_best_location_pair(
        self,
        origin_candidates: List[ExactLocation],
        dest_candidates: List[ExactLocation],
        expected_distance_miles: Optional[float] = None,
        tolerance: float = 0.3
    ) -> Tuple[ExactLocation, ExactLocation, Dict]:
        """
        Find the best origin-destination pair that matches expected distance.

        Args:
            origin_candidates: List of origin location candidates
            dest_candidates: List of destination location candidates
            expected_distance_miles: Expected trip distance in miles
            tolerance: Acceptable relative error

        Returns:
            Tuple of (best_origin, best_destination, metrics_dict)
        """
        logger.info(f"Searching for best location pair among {len(origin_candidates)} origins and {len(dest_candidates)} destinations")

        if expected_distance_miles is not None:
            logger.info(f"Target distance: {expected_distance_miles:.2f} miles (tolerance: {tolerance*100:.0f}%)")

        best_origin = origin_candidates[0]
        best_dest = dest_candidates[0]
        best_distance_km = 0.0
        best_duration_min = 0.0
        best_error = float('inf')

        trials = []

        # Try all combinations
        for i, origin in enumerate(origin_candidates):
            for j, dest in enumerate(dest_candidates):
                logger.debug(f"Testing pair {i+1},{j+1}: origin ({origin.latitude:.4f}, {origin.longitude:.4f}) -> dest ({dest.latitude:.4f}, {dest.longitude:.4f})")

                # Get distance and duration
                distance_km, duration_min = self.get_distance_and_duration(origin, dest)
                distance_miles = distance_km * 0.621371

                # Calculate error
                error = float('inf')
                if expected_distance_miles is not None and expected_distance_miles > 0:
                    error = abs(distance_miles - expected_distance_miles) / expected_distance_miles

                logger.debug(f"  Result: {distance_miles:.2f} miles, error: {error*100:.1f}%")

                trials.append({
                    'origin_idx': i,
                    'dest_idx': j,
                    'distance_miles': distance_miles,
                    'error_pct': error * 100 if error != float('inf') else None
                })

                # Update best if this is closer to target
                if error < best_error:
                    best_origin = origin
                    best_dest = dest
                    best_distance_km = distance_km
                    best_duration_min = duration_min
                    best_error = error

                    logger.info(f"  ✓ New best pair found! Distance: {distance_miles:.2f} miles, error: {error*100:.1f}%")

                # If within tolerance, we can stop early
                if expected_distance_miles is not None and error <= tolerance:
                    logger.info(f"  ✓ Found acceptable match within tolerance!")
                    break
            else:
                continue
            break  # Break outer loop if inner loop broke

        # Log final results
        best_distance_miles = best_distance_km * 0.621371
        logger.info(f"Best pair selected: origin zone {best_origin.zone_id} -> dest zone {best_dest.zone_id}")
        logger.info(f"  Distance: {best_distance_miles:.2f} miles, Duration: {best_duration_min:.1f} min")
        if expected_distance_miles is not None:
            logger.info(f"  Expected: {expected_distance_miles:.2f} miles, Error: {best_error*100:.1f}%")
            logger.info(f"  Within tolerance: {best_error <= tolerance}")

        metrics = {
            'num_trials': len(trials),
            'best_error': best_error if best_error != float('inf') else None,
            'best_distance_miles': best_distance_miles,
            'trials': trials
        }

        return best_origin, best_dest, metrics

    def augment_trip(
        self,
        pickup_zone_id: int,
        dropoff_zone_id: int,
        pickup_zone_name: str,
        dropoff_zone_name: str,
        expected_distance_miles: Optional[float] = None,
        tolerance: float = 0.3,
        use_smart_sampling: bool = True
    ) -> Dict:
        """
        Augment a trip with exact coordinates.

        Args:
            pickup_zone_id: Pickup zone ID
            dropoff_zone_id: Dropoff zone ID
            pickup_zone_name: Pickup zone name
            dropoff_zone_name: Dropoff zone name
            expected_distance_miles: Expected trip distance in miles (for validation)
            tolerance: Acceptable relative error (0.3 = 30%)
            use_smart_sampling: If True, sample multiple candidates and pick best match

        Returns:
            Dictionary with augmented trip data
        """
        logger.info(f"="*80)
        logger.info(f"Augmenting trip: {pickup_zone_name} (ID {pickup_zone_id}) -> {dropoff_zone_name} (ID {dropoff_zone_id})")
        if expected_distance_miles is not None:
            logger.info(f"Expected distance: {expected_distance_miles:.2f} miles")

        if use_smart_sampling and expected_distance_miles is not None:
            # Smart sampling: generate multiple candidates and find best match
            logger.info(f"Using SMART SAMPLING with {self.num_origin_samples} origin × {self.num_dest_samples} dest candidates")

            # Generate candidates
            origin_candidates = self._generate_location_candidates(
                pickup_zone_id,
                pickup_zone_name,
                self.num_origin_samples
            )

            dest_candidates = self._generate_location_candidates(
                dropoff_zone_id,
                dropoff_zone_name,
                self.num_dest_samples
            )

            # Find best pair
            pickup_loc, dropoff_loc, metrics = self._find_best_location_pair(
                origin_candidates,
                dest_candidates,
                expected_distance_miles,
                tolerance
            )

            distance_km = metrics['best_distance_miles'] / 0.621371
            duration_min = (distance_km / 20.0) * 60  # Estimate from distance

            # Re-query for accurate duration
            _, duration_min = self.get_distance_and_duration(pickup_loc, dropoff_loc)

            is_valid = metrics['best_error'] <= tolerance if metrics['best_error'] is not None else False

            result = {
                'pickup_location': pickup_loc.to_dict(),
                'dropoff_location': dropoff_loc.to_dict(),
                'estimated_distance_km': distance_km,
                'estimated_distance_miles': metrics['best_distance_miles'],
                'estimated_duration_minutes': duration_min,
                'expected_distance_miles': expected_distance_miles,
                'is_distance_valid': is_valid,
                'distance_error_pct': metrics['best_error'] * 100 if metrics['best_error'] is not None else None,
                'num_trials': metrics['num_trials'],
                'sampling_method': 'smart'
            }

        else:
            # Simple sampling: use zone centers
            logger.info("Using SIMPLE SAMPLING (zone centers only)")

            # Geocode pickup and dropoff
            pickup_loc = self.geocode_zone(pickup_zone_id, pickup_zone_name)
            dropoff_loc = self.geocode_zone(dropoff_zone_id, dropoff_zone_name)

            # Get distance and duration
            distance_km, duration_min = self.get_distance_and_duration(pickup_loc, dropoff_loc)
            distance_miles = distance_km * 0.621371  # km to miles

            # Validate against expected distance if provided
            is_valid = True
            error_pct = None
            if expected_distance_miles is not None and expected_distance_miles > 0:
                error = abs(distance_miles - expected_distance_miles) / expected_distance_miles
                error_pct = error * 100
                is_valid = error <= tolerance
                logger.info(f"Distance error: {error_pct:.1f}% (valid: {is_valid})")

            result = {
                'pickup_location': pickup_loc.to_dict(),
                'dropoff_location': dropoff_loc.to_dict(),
                'estimated_distance_km': distance_km,
                'estimated_distance_miles': distance_miles,
                'estimated_duration_minutes': duration_min,
                'expected_distance_miles': expected_distance_miles,
                'is_distance_valid': is_valid,
                'distance_error_pct': error_pct,
                'num_trials': 1,
                'sampling_method': 'simple'
            }

        logger.info(f"Augmentation complete: {result['estimated_distance_miles']:.2f} miles, {result['estimated_duration_minutes']:.1f} min")
        logger.info(f"="*80 + "\n")

        return result

    def augment_dataframe(
        self,
        df: pd.DataFrame,
        max_samples: Optional[int] = None,
        rate_limit_delay: float = 0.1,
        use_smart_sampling: bool = True
    ) -> pd.DataFrame:
        """
        Augment a DataFrame of trips with exact coordinates.

        Args:
            df: DataFrame with trip data
            max_samples: Maximum number of trips to augment (None = all)
            rate_limit_delay: Delay between API calls in seconds
            use_smart_sampling: If True, use smart sampling for better distance matching

        Returns:
            DataFrame with augmented location data
        """
        logger.info(f"Starting batch augmentation of {len(df)} trips")

        if max_samples is not None:
            df = df.head(max_samples)
            logger.info(f"Limited to {max_samples} samples")

        logger.info(f"Smart sampling: {use_smart_sampling}, Rate limit delay: {rate_limit_delay}s")

        augmented_data = []
        successful = 0
        failed = 0

        for idx, row in df.iterrows():
            try:
                logger.info(f"\nProcessing trip {idx + 1}/{len(df)}")

                augmentation = self.augment_trip(
                    pickup_zone_id=row['PULocationID'],
                    dropoff_zone_id=row['DOLocationID'],
                    pickup_zone_name=row.get('pickup_zone', 'Unknown'),
                    dropoff_zone_name=row.get('dropoff_zone', 'Unknown'),
                    expected_distance_miles=row.get('trip_miles', None),
                    use_smart_sampling=use_smart_sampling
                )

                # Merge with original row
                augmented_row = {**row.to_dict(), **augmentation}
                augmented_data.append(augmented_row)
                successful += 1

                # Rate limiting
                time.sleep(rate_limit_delay)

                if (idx + 1) % 10 == 0:
                    logger.info(f"Progress: {idx + 1}/{len(df)} trips completed ({successful} successful, {failed} failed)")

            except Exception as e:
                failed += 1
                logger.error(f"FAILED to augment trip {idx}: {e}", exc_info=True)
                continue

        logger.info(f"\nBatch augmentation complete!")
        logger.info(f"  Successful: {successful}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Total: {len(augmented_data)}")

        return pd.DataFrame(augmented_data)

    def save_cache(self, filepath: str):
        """Save location cache to JSON file."""
        logger.info(f"Saving location cache to {filepath}")

        cache_data = {
            str(zone_id): [loc.to_dict() for loc in locs]
            for zone_id, locs in self.location_cache.items()
        }

        with open(filepath, 'w') as f:
            json.dump(cache_data, f, indent=2)

        total_locations = sum(len(locs) for locs in self.location_cache.values())
        logger.info(f"Saved location cache: {len(self.location_cache)} zones, {total_locations} locations")

    def load_cache(self, filepath: str):
        """Load location cache from JSON file."""
        logger.info(f"Loading location cache from {filepath}")

        with open(filepath, 'r') as f:
            cache_data = json.load(f)

        self.location_cache = {}
        for zone_id_str, locs_list in cache_data.items():
            zone_id = int(zone_id_str)
            self.location_cache[zone_id] = [ExactLocation(**loc) for loc in locs_list]

        total_locations = sum(len(locs) for locs in self.location_cache.values())
        logger.info(f"Loaded location cache: {len(self.location_cache)} zones, {total_locations} locations")

    def print_statistics(self):
        """Print detailed statistics about API usage and performance."""
        logger.info("\n" + "="*80)
        logger.info("LOCATION AUGMENTATION STATISTICS")
        logger.info("="*80)

        logger.info("\nAPI Usage:")
        logger.info(f"  Total API calls: {self.stats['total_api_calls']}")
        logger.info(f"  Cache hits: {self.stats['cache_hits']}")
        logger.info(f"  Cache misses: {self.stats['cache_misses']}")

        if self.stats['cache_hits'] + self.stats['cache_misses'] > 0:
            hit_rate = self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses'])
            logger.info(f"  Cache hit rate: {hit_rate*100:.1f}%")

        logger.info("\nFailures:")
        logger.info(f"  Geocoding failures: {self.stats['geocoding_failures']}")
        logger.info(f"  Direction API failures: {self.stats['direction_failures']}")

        logger.info("\nCache Status:")
        logger.info(f"  Zones cached: {len(self.location_cache)}")
        total_locations = sum(len(locs) for locs in self.location_cache.values())
        logger.info(f"  Total locations cached: {total_locations}")

        logger.info("="*80 + "\n")


def main():
    """Example usage of location augmenter with smart sampling."""
    print("\n" + "="*80)
    print("LOCATION AUGMENTATION DEMO - Smart Sampling")
    print("="*80 + "\n")

    taxi_zone_lookup = "/home/hengyu/CS294-Agentic-AI/Agentic-AI/taxi_zone_lookup.csv"

    # Create augmenter with smart sampling
    augmenter = LocationAugmenter(
        taxi_zone_lookup,
        num_origin_samples=3,
        num_dest_samples=3
    )

    # Example 1: Smart sampling (default)
    print("\n" + "="*80)
    print("EXAMPLE 1: Smart Sampling (3×3 candidates)")
    print("="*80)

    augmented_trip = augmenter.augment_trip(
        pickup_zone_id=230,  # Times Square
        dropoff_zone_id=132,  # JFK Airport
        pickup_zone_name="Times Sq/Theatre District",
        dropoff_zone_name="JFK Airport",
        expected_distance_miles=16.5,
        use_smart_sampling=True
    )

    print(f"\nRESULTS:")
    print(f"  Pickup: {augmented_trip['pickup_location']['zone_name']}")
    print(f"    Coordinates: ({augmented_trip['pickup_location']['latitude']:.4f}, {augmented_trip['pickup_location']['longitude']:.4f})")
    print(f"  Dropoff: {augmented_trip['dropoff_location']['zone_name']}")
    print(f"    Coordinates: ({augmented_trip['dropoff_location']['latitude']:.4f}, {augmented_trip['dropoff_location']['longitude']:.4f})")
    print(f"\n  Estimated Distance: {augmented_trip['estimated_distance_miles']:.2f} miles")
    print(f"  Expected Distance: {augmented_trip['expected_distance_miles']:.2f} miles")
    print(f"  Distance Error: {augmented_trip['distance_error_pct']:.1f}%")
    print(f"  Estimated Duration: {augmented_trip['estimated_duration_minutes']:.1f} minutes")
    print(f"  Valid: {augmented_trip['is_distance_valid']}")
    print(f"  Trials: {augmented_trip['num_trials']}")
    print(f"  Method: {augmented_trip['sampling_method']}")

    # Example 2: Simple sampling (for comparison)
    print("\n" + "="*80)
    print("EXAMPLE 2: Simple Sampling (zone centers only)")
    print("="*80)

    augmented_trip_simple = augmenter.augment_trip(
        pickup_zone_id=230,  # Times Square
        dropoff_zone_id=132,  # JFK Airport
        pickup_zone_name="Times Sq/Theatre District",
        dropoff_zone_name="JFK Airport",
        expected_distance_miles=16.5,
        use_smart_sampling=False
    )

    print(f"\nRESULTS:")
    print(f"  Estimated Distance: {augmented_trip_simple['estimated_distance_miles']:.2f} miles")
    print(f"  Expected Distance: {augmented_trip_simple['expected_distance_miles']:.2f} miles")
    print(f"  Distance Error: {augmented_trip_simple['distance_error_pct']:.1f}%")
    print(f"  Valid: {augmented_trip_simple['is_distance_valid']}")
    print(f"  Method: {augmented_trip_simple['sampling_method']}")

    # Print statistics
    augmenter.print_statistics()

    # Save cache
    output_dir = Path("data/cache")
    output_dir.mkdir(parents=True, exist_ok=True)
    augmenter.save_cache(output_dir / "location_cache.json")

    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
