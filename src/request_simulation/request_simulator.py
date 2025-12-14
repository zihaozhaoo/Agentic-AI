"""
Request Simulator - Main Orchestrator

This module orchestrates the complete request simulation pipeline:
1. Load and preprocess trip data
2. Augment with exact coordinates
3. Assign POIs and customer profiles
4. Generate natural language requests (50% template, 50% LLM)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import random
from datetime import datetime, timedelta

from .data_preprocessing import NYCTripDataPreprocessor
from .poi_database import POIDatabase
from .customer_profiles import CustomerProfileDatabase
from .location_augmentation import LocationAugmenter
from .template_generator import TemplateGenerator
from .llm_generator import LLMGenerator


class RequestSimulator:
    """Main orchestrator for request simulation."""

    def __init__(
        self,
        taxi_zone_lookup_path: str,
        google_maps_api_key: Optional[str] = None,
        llm_provider: str = "openai",
        llm_api_key: Optional[str] = None,
        use_location_cache: bool = True,
        num_origin_samples: int = 3,
        num_dest_samples: int = 3,
        template_ratio: float = 0.5
    ):
        """
        Initialize request simulator.

        Args:
            taxi_zone_lookup_path: Path to taxi zone lookup CSV
            google_maps_api_key: Google Maps API key
            llm_provider: LLM provider ("openai" or "anthropic")
            llm_api_key: LLM API key
            use_location_cache: Whether to cache location augmentation results
            num_origin_samples: Number of origin candidates for smart sampling
            num_dest_samples: Number of destination candidates for smart sampling
            template_ratio: Ratio of template-based vs LLM-based generation (0.5 = 50/50)
        """
        print("Initializing Request Simulator...")

        self.template_ratio = template_ratio

        # Initialize preprocessor
        print("  - Loading taxi zone lookup...")
        self.preprocessor = NYCTripDataPreprocessor(taxi_zone_lookup_path)

        # Initialize POI database
        print("  - Initializing POI database...")
        self.poi_db = POIDatabase(taxi_zone_lookup_path)

        # Initialize customer profile database
        print("  - Initializing customer profile database...")
        self.customer_db = CustomerProfileDatabase(taxi_zone_lookup_path)

        # Initialize location augmenter
        print("  - Initializing location augmenter...")
        self.location_augmenter = LocationAugmenter(
            taxi_zone_lookup_path,
            google_maps_api_key,
            use_cache=use_location_cache,
            num_origin_samples=num_origin_samples,
            num_dest_samples=num_dest_samples
        )
        print(f"    Smart sampling: {num_origin_samples}×{num_dest_samples} candidates")

        # Initialize generators
        print("  - Initializing template generator...")
        self.template_gen = TemplateGenerator()

        print(f"  - Initializing LLM generator ({llm_provider})...")
        try:
            self.llm_gen = LLMGenerator(provider=llm_provider, api_key=llm_api_key)
        except Exception as e:
            print(f"    Warning: LLM generator initialization failed: {e}")
            print("    Falling back to template-only generation")
            self.llm_gen = None
            self.template_ratio = 1.0

        print("Initialization complete!\n")

    def load_and_preprocess_data(
        self,
        parquet_path: str,
        sample_size: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load and preprocess trip data.

        Args:
            parquet_path: Path to parquet file
            sample_size: Optional sample size

        Returns:
            Preprocessed DataFrame
        """
        print(f"Loading data from {parquet_path}...")
        return self.preprocessor.preprocess_pipeline(parquet_path, sample_size)

    def augment_trip_with_context(
        self,
        trip_row: pd.Series,
        augment_location: bool = False
    ) -> Dict[str, Any]:
        """
        Augment a single trip with contextual information.

        Args:
            trip_row: Trip data row from DataFrame
            augment_location: Whether to augment with exact coordinates (slow)

        Returns:
            Augmented trip data dictionary
        """
        trip_data = {
            'trip_id': trip_row.name,
            'pickup_zone_id': trip_row['PULocationID'],
            'dropoff_zone_id': trip_row['DOLocationID'],
            'pickup_zone': trip_row.get('pickup_zone', 'Unknown'),
            'dropoff_zone': trip_row.get('dropoff_zone', 'Unknown'),
            'pickup_borough': trip_row.get('pickup_borough', 'Unknown'),
            'dropoff_borough': trip_row.get('dropoff_borough', 'Unknown'),
            'request_time': trip_row.get('request_datetime', datetime.now()),
            'trip_miles': trip_row.get('trip_miles', 0),
            'trip_time': trip_row.get('trip_time', 0),
            # Use actual passenger count if available; otherwise default to 1
            'passenger_count': trip_row.get('passenger_count', 1),
            'wav_request_flag': trip_row.get('wav_request_flag', 'N'),
            'shared_request_flag': trip_row.get('shared_request_flag', 'N'),

            # Raw datetime fields from original data (for validation)
            'raw_request_datetime': trip_row.get('request_datetime'),
            'raw_pickup_datetime': trip_row.get('pickup_datetime'),
            'raw_dropoff_datetime': trip_row.get('dropoff_datetime'),

            # Time window fields
            'requested_pickup_time': trip_row.get('requested_pickup_time'),
            'requested_dropoff_time': trip_row.get('requested_dropoff_time'),
            'has_arrival_constraint': trip_row.get('has_arrival_constraint', False),
            'pickup_window_minutes': trip_row.get('pickup_window_minutes'),
            'dropoff_window_minutes': trip_row.get('dropoff_window_minutes'),
            'is_tight_constraint': trip_row.get('is_tight_constraint', False),
            'available_trip_time_minutes': trip_row.get('available_trip_time_minutes'),
            'actual_trip_duration_minutes': trip_row.get('actual_trip_duration_minutes'),
        }

        # Add POI references
        pickup_pois = self.poi_db.sample_pois_for_zone(trip_row['PULocationID'])
        dropoff_pois = self.poi_db.sample_pois_for_zone(trip_row['DOLocationID'])

        if pickup_pois:
            trip_data['pickup_poi'] = random.choice(pickup_pois)
        if dropoff_pois:
            trip_data['dropoff_poi'] = random.choice(dropoff_pois)

        # Assign customer profile (30% probability)
        customer_profile = self.customer_db.assign_profile_to_trip(
            trip_row['PULocationID'],
            trip_row['DOLocationID'],
            probability_personal=0.3
        )

        if customer_profile:
            # Check if pickup/dropoff match any personal locations
            pickup_personal = None
            dropoff_personal = None

            if customer_profile.home.zone_id == trip_row['PULocationID']:
                pickup_personal = 'home'
            elif customer_profile.work and customer_profile.work.zone_id == trip_row['PULocationID']:
                pickup_personal = 'work'

            if customer_profile.home.zone_id == trip_row['DOLocationID']:
                dropoff_personal = 'home'
            elif customer_profile.work and customer_profile.work.zone_id == trip_row['DOLocationID']:
                dropoff_personal = 'work'

            trip_data['customer_id'] = customer_profile.customer_id
            trip_data['pickup_personal'] = pickup_personal
            trip_data['dropoff_personal'] = dropoff_personal

        # Optionally augment with exact location (expensive API call)
        if augment_location:
            # Use smart sampling setting if available
            use_smart = getattr(self, '_use_smart_sampling', True)

            augmentation = self.location_augmenter.augment_trip(
                trip_row['PULocationID'],
                trip_row['DOLocationID'],
                trip_data['pickup_zone'],
                trip_data['dropoff_zone'],
                trip_row.get('trip_miles', None),
                use_smart_sampling=use_smart
            )

            trip_data['pickup_lat'] = augmentation['pickup_location']['latitude']
            trip_data['pickup_lon'] = augmentation['pickup_location']['longitude']
            trip_data['pickup_address'] = augmentation['pickup_location'].get('address')
            trip_data['dropoff_lat'] = augmentation['dropoff_location']['latitude']
            trip_data['dropoff_lon'] = augmentation['dropoff_location']['longitude']
            trip_data['dropoff_address'] = augmentation['dropoff_location'].get('address')
            trip_data['estimated_duration_minutes'] = augmentation['estimated_duration_minutes']
            trip_data['distance_error_pct'] = augmentation.get('distance_error_pct')
            trip_data['sampling_method'] = augmentation.get('sampling_method')

        else:
            # Estimate duration from trip_time if available
            trip_data['estimated_duration_minutes'] = trip_row.get('trip_time', 1800) / 60

        return trip_data

    def generate_nl_request(self, trip_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a natural language request for a trip.

        Args:
            trip_data: Augmented trip data

        Returns:
            Dictionary with generated request and metadata
        """
        # Decide whether to use template or LLM
        use_template = random.random() < self.template_ratio

        if use_template or self.llm_gen is None:
            # Template-based generation
            result = self.template_gen.generate(trip_data)
        else:
            # LLM-based generation
            try:
                result = self.llm_gen.generate(trip_data)
            except Exception as e:
                print(f"LLM generation failed, falling back to template: {e}")
                result = self.template_gen.generate(trip_data)

        # Merge with trip data
        return {**trip_data, **result}

    def simulate_requests(
        self,
        df: pd.DataFrame,
        n_requests: Optional[int] = None,
        augment_location: bool = False,
        use_smart_sampling: bool = True,
        save_output: Optional[str] = None,
        mean_interarrival_seconds: Optional[float] = 15.0,
        start_time: Optional[datetime] = None,
        uniform_zone_sampling: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Simulate natural language requests for a batch of trips.

        Args:
            df: Preprocessed trip DataFrame
            n_requests: Number of requests to generate (None = all)
            augment_location: Whether to augment with exact coordinates
            use_smart_sampling: Whether to use smart sampling for location augmentation
            save_output: Optional path to save output JSON
            mean_interarrival_seconds: Target mean interarrival time between requests (in seconds).
                Smaller values create busier periods with fewer idle vehicles. Set to None to keep
                original timestamps from the dataset.
            start_time: Optional start time for rescheduled requests. Defaults to earliest
                request time in the sampled DataFrame or now() if missing.
            uniform_zone_sampling: If True, sample pickup zones uniformly to avoid clustering
                around historical hotspots.

        Returns:
            List of simulated request dictionaries
        """
        # Balanced sampling to avoid concentrated pickup zones
        df = self._sample_requests(
            df,
            n_requests=n_requests or len(df),
            uniform_zone_sampling=uniform_zone_sampling
        )

        # Keep a copy of the original request timestamps for duration alignment when rescheduling
        original_request_times = df['request_datetime'].copy() if 'request_datetime' in df.columns else None

        # Densify request arrival times to keep vehicles busy and create overlapping trips
        if mean_interarrival_seconds is not None:
            df = self._reschedule_request_times(
                df=df,
                original_request_times=original_request_times,
                start_time=start_time,
                mean_interarrival_seconds=mean_interarrival_seconds
            )

        print(f"\nSimulating {len(df)} ride requests...")
        print(f"  - Template ratio: {self.template_ratio * 100:.0f}%")
        print(f"  - LLM ratio: {(1 - self.template_ratio) * 100:.0f}%")
        print(f"  - Location augmentation: {'ON' if augment_location else 'OFF'}")
        if augment_location:
            print(f"  - Smart sampling: {'ON' if use_smart_sampling else 'OFF'}")
        if mean_interarrival_seconds is not None:
            print(f"  - Mean interarrival: {mean_interarrival_seconds:.0f} seconds")
        print(f"  - Uniform pickup zones: {'ON' if uniform_zone_sampling else 'OFF'}")
        print()

        # Store use_smart_sampling for augment_trip_with_context
        self._use_smart_sampling = use_smart_sampling

        requests = []

        for idx, row in df.iterrows():
            # Augment trip with context
            trip_data = self.augment_trip_with_context(row, augment_location)

            # Generate NL request
            request_data = self.generate_nl_request(trip_data)

            requests.append(request_data)

            if (idx + 1) % 50 == 0:
                print(f"  Generated {idx + 1} / {len(df)} requests...")

        print(f"\nCompleted simulation of {len(requests)} requests!")

        # Save output if requested
        if save_output:
            self.save_requests(requests, save_output)

        return requests

    def _sample_requests(
        self,
        df: pd.DataFrame,
        n_requests: int,
        uniform_zone_sampling: bool
    ) -> pd.DataFrame:
        """
        Sample requests with optional uniform pickup zone weighting.

        Args:
            df: Preprocessed trip DataFrame
            n_requests: Number of requests to sample (with replacement if needed)
            uniform_zone_sampling: Whether to flatten pickup zone distribution

        Returns:
            Sampled DataFrame
        """
        if n_requests <= 0:
            return df.head(0)

        # Compute weights to balance pickup zones
        weights = None
        if uniform_zone_sampling and 'PULocationID' in df.columns:
            weights = self._compute_zone_balanced_weights(df['PULocationID'])

        replace = n_requests > len(df)
        sampled = df.sample(
            n=n_requests,
            replace=replace,
            weights=weights,
            random_state=42
        ).reset_index(drop=True)
        return sampled

    def _compute_zone_balanced_weights(self, pu_series: pd.Series) -> pd.Series:
        """
        Build inverse-frequency weights to sample pickup zones more uniformly.

        Args:
            pu_series: Series of pickup zone IDs

        Returns:
            Series of normalized weights aligned with the input index
        """
        counts = pu_series.value_counts()
        # Inverse frequency; rare zones get higher weight
        inv_freq = pu_series.map(lambda x: 1.0 / counts.get(x, 1))
        normalized = inv_freq / inv_freq.sum()
        return normalized

    def _reschedule_request_times(
        self,
        df: pd.DataFrame,
        original_request_times: Optional[pd.Series],
        start_time: Optional[datetime],
        mean_interarrival_seconds: float
    ) -> pd.DataFrame:
        """
        Reschedule request timestamps to produce a high-demand arrival process.

        Args:
            df: DataFrame of sampled trips
            original_request_times: Original request_datetime column (if present)
            start_time: Optional fixed start time for the first request
            mean_interarrival_seconds: Mean interarrival time to target

        Returns:
            DataFrame with updated request/related timestamps
        """
        # Work on a copy to avoid mutating caller state
        df_out = df.copy()

        # Choose a deterministic base to anchor the dense timeline
        base_time = start_time
        if base_time is None:
            if original_request_times is not None and len(original_request_times) > 0:
                base_time = original_request_times.min().to_pydatetime()
            else:
                base_time = datetime.now()

        # Build exponential interarrival times to mimic high-utilization demand
        interarrivals = np.random.exponential(scale=mean_interarrival_seconds, size=len(df_out))
        cumulative_seconds = np.cumsum(interarrivals)
        new_request_times = [base_time + timedelta(seconds=float(s)) for s in cumulative_seconds]
        df_out['request_datetime'] = new_request_times

        # Shift related pickup/dropoff timestamps to maintain realistic offsets
        if original_request_times is not None:
            time_offsets = original_request_times.reset_index(drop=True)
            df_out = self._shift_time_columns(df_out, time_offsets, new_request_times)

        return df_out

    def _shift_time_columns(
        self,
        df: pd.DataFrame,
        original_request_times: pd.Series,
        new_request_times: List[datetime]
    ) -> pd.DataFrame:
        """
        Shift downstream timestamps (pickup/dropoff windows) to stay consistent with the new request time.

        Args:
            df: DataFrame with timing columns
            original_request_times: Original request times from the source data
            new_request_times: New dense request times

        Returns:
            DataFrame with adjusted pickup/dropoff related columns
        """
        df_out = df.copy()
        columns_to_shift = [
            'pickup_datetime',
            'dropoff_datetime',
            'requested_pickup_time',
            'requested_dropoff_time'
        ]

        # Compute per-row offsets and apply them to the new arrival time
        for col in columns_to_shift:
            if col not in df_out.columns:
                continue
            offsets = df_out[col] - original_request_times
            shifted = []
            for idx, offset in enumerate(offsets):
                if pd.isna(offset):
                    shifted.append(None)
                    continue
                shifted.append(new_request_times[idx] + offset)
            df_out[col] = shifted

        return df_out

    def save_requests(self, requests: List[Dict[str, Any]], filepath: str):
        """
        Save simulated requests to JSON file.

        Args:
            requests: List of request dictionaries
            filepath: Output file path
        """
        # Convert datetime objects to strings for JSON serialization
        serializable_requests = []

        for req in requests:
            req_copy = req.copy()

            for key, value in req_copy.items():
                if isinstance(value, (datetime, pd.Timestamp)):
                    req_copy[key] = value.isoformat()
                elif isinstance(value, (np.integer, np.floating)):
                    req_copy[key] = value.item()

            serializable_requests.append(req_copy)

        # Save to file
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(serializable_requests, f, indent=2)

        print(f"\nSaved {len(requests)} requests to {filepath}")

    def get_statistics(self, requests: List[Dict[str, Any]]) -> Dict:
        """Get statistics about generated requests."""
        total = len(requests)

        generation_methods = {}
        tiers = {}

        for req in requests:
            method = req.get('generation_method', 'unknown')
            generation_methods[method] = generation_methods.get(method, 0) + 1

            tier = req.get('tier', 'N/A')
            if tier != 'N/A':
                tiers[tier] = tiers.get(tier, 0) + 1

        return {
            'total_requests': total,
            'generation_methods': generation_methods,
            'template_tiers': tiers
        }


def main():
    """Example usage of request simulator."""

    # Configuration: assume running inside the project checkout
    project_root = Path(__file__).resolve().parent.parent.parent
    taxi_zone_lookup = project_root / "taxi_zone_lookup.csv"
    # Keep the large parquet file one level above the repo by default
    parquet_file = project_root.parent / "fhvhv_tripdata_2025-01.parquet"

    # Initialize simulator
    simulator = RequestSimulator(
        taxi_zone_lookup_path=str(taxi_zone_lookup),
        llm_provider="openai",  # or "anthropic"
        template_ratio=0.5  # 50% template, 50% LLM
    )

    # Load and preprocess data
    df = simulator.load_and_preprocess_data(str(parquet_file), sample_size=1000)

    # Generate customer profiles
    print("Generating customer profiles...")
    simulator.customer_db.generate_profiles(200)

    # Simulate requests
    requests = simulator.simulate_requests(
        df,
        n_requests=100,
        augment_location=False,  # Set to True to use Google Maps API
        save_output="data/output/simulated_requests.json"
    )

    # Print statistics
    print("\n" + "="*80)
    print("SIMULATION STATISTICS")
    print("="*80)

    stats = simulator.get_statistics(requests)
    print(f"\nTotal Requests: {stats['total_requests']}")

    print(f"\nGeneration Methods:")
    for method, count in stats['generation_methods'].items():
        pct = (count / stats['total_requests']) * 100
        print(f"  {method}: {count} ({pct:.1f}%)")

    print(f"\nTemplate Tiers:")
    for tier, count in stats['template_tiers'].items():
        pct = (count / sum(stats['template_tiers'].values())) * 100
        print(f"  {tier}: {count} ({pct:.1f}%)")

    # Print some examples
    print("\n" + "="*80)
    print("EXAMPLE REQUESTS")
    print("="*80)

    for i, req in enumerate(random.sample(requests, min(5, len(requests)))):
        print(f"\n--- Request {i+1} ---")
        print(f"Method: {req.get('generation_method', 'unknown')}")
        if req.get('tier'):
            print(f"Tier: {req.get('tier')}")
        print(f"Request: {req.get('request', 'N/A')}")
        print(f"From: {req.get('pickup_zone', 'Unknown')}")
        print(f"To: {req.get('dropoff_zone', 'Unknown')}")


if __name__ == "__main__":
    main()
