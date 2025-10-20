"""
Data Preprocessing Module for NYC HVFHV Trip Data

This module handles reading, cleaning, and preprocessing NYC TLC High-Volume
For-Hire Vehicle trip data from Parquet files.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta


class NYCTripDataPreprocessor:
    """Preprocessor for NYC HVFHV trip data."""

    def __init__(self, taxi_zone_lookup_path: str):
        """
        Initialize the preprocessor.

        Args:
            taxi_zone_lookup_path: Path to taxi zone lookup CSV file
        """
        self.zone_lookup = pd.read_csv(taxi_zone_lookup_path)
        self.zone_lookup_dict = self.zone_lookup.set_index('LocationID').to_dict('index')

    def load_parquet(self, parquet_path: str, sample_size: Optional[int] = None) -> pd.DataFrame:
        """
        Load trip data from Parquet file.

        Args:
            parquet_path: Path to the Parquet file
            sample_size: Optional number of rows to sample (None = load all)

        Returns:
            DataFrame with trip records
        """
        df = pd.read_parquet(parquet_path)

        if sample_size is not None:
            df = df.sample(n=min(sample_size, len(df)), random_state=42)

        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and filter trip data.

        Args:
            df: Raw trip DataFrame

        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()

        # Remove invalid LocationIDs
        valid_location_ids = set(self.zone_lookup['LocationID'].values)
        df_clean = df_clean[
            df_clean['PULocationID'].isin(valid_location_ids) &
            df_clean['DOLocationID'].isin(valid_location_ids)
        ]

        # Remove records with same pickup and dropoff
        df_clean = df_clean[df_clean['PULocationID'] != df_clean['DOLocationID']]

        # Remove invalid trip miles (negative or zero)
        df_clean = df_clean[df_clean['trip_miles'] > 0]

        # Remove invalid trip times (negative or zero)
        df_clean = df_clean[df_clean['trip_time'] > 0]

        # Convert datetime columns if they're strings
        datetime_cols = ['request_datetime', 'pickup_datetime', 'dropoff_datetime']
        for col in datetime_cols:
            if col in df_clean.columns and not pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                df_clean[col] = pd.to_datetime(df_clean[col])

        # Remove records with inconsistent timestamps
        if all(col in df_clean.columns for col in ['request_datetime', 'pickup_datetime', 'dropoff_datetime']):
            df_clean = df_clean[
                (df_clean['request_datetime'] <= df_clean['pickup_datetime']) &
                (df_clean['pickup_datetime'] <= df_clean['dropoff_datetime'])
            ]

        # Remove extreme outliers (trips > 100 miles or > 4 hours)
        df_clean = df_clean[df_clean['trip_miles'] <= 100]
        df_clean = df_clean[df_clean['trip_time'] <= 14400]  # 4 hours in seconds

        return df_clean.reset_index(drop=True)

    def enrich_with_zone_info(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add zone information (borough, zone name) to trips.

        Args:
            df: Trip DataFrame

        Returns:
            Enriched DataFrame with zone information
        """
        df_enriched = df.copy()

        # Add pickup zone info
        df_enriched['pickup_borough'] = df_enriched['PULocationID'].map(
            lambda x: self.zone_lookup_dict.get(x, {}).get('Borough', 'Unknown')
        )
        df_enriched['pickup_zone'] = df_enriched['PULocationID'].map(
            lambda x: self.zone_lookup_dict.get(x, {}).get('Zone', 'Unknown')
        )

        # Add dropoff zone info
        df_enriched['dropoff_borough'] = df_enriched['DOLocationID'].map(
            lambda x: self.zone_lookup_dict.get(x, {}).get('Borough', 'Unknown')
        )
        df_enriched['dropoff_zone'] = df_enriched['DOLocationID'].map(
            lambda x: self.zone_lookup_dict.get(x, {}).get('Zone', 'Unknown')
        )

        return df_enriched

    def extract_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract temporal features from request datetime.

        Args:
            df: Trip DataFrame with request_datetime

        Returns:
            DataFrame with added temporal features
        """
        df_temporal = df.copy()

        if 'request_datetime' in df_temporal.columns:
            df_temporal['hour_of_day'] = df_temporal['request_datetime'].dt.hour
            df_temporal['day_of_week'] = df_temporal['request_datetime'].dt.dayofweek
            df_temporal['is_weekend'] = df_temporal['day_of_week'].isin([5, 6])
            df_temporal['is_rush_hour'] = df_temporal['hour_of_day'].isin([7, 8, 9, 17, 18, 19])

        return df_temporal

    def generate_time_windows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate pickup and dropoff time windows based on actual trip times.

        This creates realistic time constraints for ride requests:
        - requested_pickup_time: When the customer wants to be picked up
        - requested_dropoff_time: When the customer needs to arrive (optional)
        - pickup_time_window: Buffer around pickup time
        - dropoff_time_window: Buffer around arrival time

        Args:
            df: Trip DataFrame with datetime columns

        Returns:
            DataFrame with added time window features
        """
        from datetime import timedelta
        import random

        df_time = df.copy()

        # Check if required columns exist
        if 'request_datetime' not in df_time.columns or 'pickup_datetime' not in df_time.columns:
            print("Warning: datetime columns not found, skipping time window generation")
            # Add placeholder columns
            df_time['requested_pickup_time'] = None
            df_time['requested_dropoff_time'] = None
            df_time['has_arrival_constraint'] = False
            df_time['pickup_window_minutes'] = 15
            df_time['dropoff_window_minutes'] = None
            df_time['is_tight_constraint'] = False
            df_time['available_trip_time_minutes'] = None
            df_time['actual_trip_duration_minutes'] = None
            return df_time

        if 'request_datetime' in df_time.columns and 'pickup_datetime' in df_time.columns:
            # Requested pickup time = close to actual pickup time (with small variation)
            # Add -5 to +5 minute variation to make it realistic
            df_time['pickup_time_variation'] = df_time.apply(
                lambda _: random.randint(-5, 5), axis=1
            )
            df_time['requested_pickup_time'] = df_time.apply(
                lambda row: row['pickup_datetime'] + timedelta(minutes=row['pickup_time_variation'])
                if pd.notna(row['pickup_datetime']) else None,
                axis=1
            )

            # Fallback: If requested_pickup_time is NaT, use raw pickup_datetime
            df_time['requested_pickup_time'] = df_time.apply(
                lambda row: row['pickup_datetime']
                if (pd.isna(row['requested_pickup_time']) or row['requested_pickup_time'] is None) and
                   pd.notna(row['pickup_datetime'])
                else row['requested_pickup_time'],
                axis=1
            )

            # For some requests, generate a desired arrival time constraint
            # Based on the actual dropoff time with some randomization
            if 'dropoff_datetime' in df_time.columns:
                # 60% of requests have arrival time constraints
                df_time['has_arrival_constraint'] = df_time.apply(
                    lambda _: random.random() < 0.6, axis=1
                )

                # Calculate actual trip duration first
                df_time['actual_trip_duration_minutes'] = df_time['trip_time'] / 60

                # Calculate requested arrival time
                # Should be close to actual dropoff time, with variation
                df_time['arrival_time_variation'] = df_time.apply(
                    lambda _: random.randint(-10, 10), axis=1
                )

                df_time['requested_dropoff_time'] = df_time.apply(
                    lambda row: row['dropoff_datetime'] + timedelta(minutes=row['arrival_time_variation'])
                    if row['has_arrival_constraint'] and pd.notna(row['dropoff_datetime']) else None,
                    axis=1
                )

                # Calculate available time for trip (requested dropoff - requested pickup)
                df_time['available_trip_time_minutes'] = df_time.apply(
                    lambda row: (row['requested_dropoff_time'] - row['requested_pickup_time']).total_seconds() / 60
                    if row['has_arrival_constraint'] and pd.notna(row['requested_dropoff_time'])
                    and pd.notna(row['requested_pickup_time'])
                    else None,
                    axis=1
                )

                # IMPORTANT: If estimated duration > actual duration, adjust requested dropoff time
                # This happens when routing takes longer than the actual trip (traffic, detours, etc.)
                # We need to give customers enough time to actually complete the trip
                df_time['estimated_duration_minutes'] = df_time.apply(
                    lambda row: max(row['actual_trip_duration_minutes'], row.get('trip_time', 0) / 60),
                    axis=1
                )

                # Adjust dropoff time if available time is less than needed
                df_time['requested_dropoff_time'] = df_time.apply(
                    lambda row: (row['requested_pickup_time'] +
                                timedelta(minutes=row['estimated_duration_minutes'] + random.randint(5, 15)))
                    if (row['has_arrival_constraint'] and pd.notna(row['requested_pickup_time']) and
                        row['available_trip_time_minutes'] is not None and
                        row['available_trip_time_minutes'] < row['actual_trip_duration_minutes'])
                    else row.get('requested_dropoff_time'),
                    axis=1
                )

                # Recalculate available time after adjustment
                df_time['available_trip_time_minutes'] = df_time.apply(
                    lambda row: (row['requested_dropoff_time'] - row['requested_pickup_time']).total_seconds() / 60
                    if row['has_arrival_constraint'] and pd.notna(row['requested_dropoff_time'])
                    and pd.notna(row['requested_pickup_time'])
                    else None,
                    axis=1
                )

                # Calculate pickup time flexibility (window)
                # Tighter windows for rush hour or time-constrained requests
                df_time['pickup_window_minutes'] = df_time.apply(
                    lambda row: random.randint(5, 10) if row.get('is_rush_hour', False)
                    else random.randint(10, 20),
                    axis=1
                )

                # Dropoff window (only for time-constrained requests)
                df_time['dropoff_window_minutes'] = df_time.apply(
                    lambda row: random.randint(5, 15) if row['has_arrival_constraint']
                    else None,
                    axis=1
                )

                # Is the time constraint tight? (available time < actual time + 10 min buffer)
                df_time['is_tight_constraint'] = df_time.apply(
                    lambda row: row['has_arrival_constraint'] and
                    row['available_trip_time_minutes'] is not None and
                    row['available_trip_time_minutes'] < (row['actual_trip_duration_minutes'] + 10),
                    axis=1
                )

                # Fallback: If requested_dropoff_time is NaT but we have arrival constraint,
                # use the raw dropoff_datetime
                df_time['requested_dropoff_time'] = df_time.apply(
                    lambda row: row['dropoff_datetime']
                    if (row['has_arrival_constraint'] and
                        (pd.isna(row['requested_dropoff_time']) or row['requested_dropoff_time'] is None) and
                        pd.notna(row['dropoff_datetime']))
                    else row['requested_dropoff_time'],
                    axis=1
                )

                # Recalculate available time one more time after fallback
                df_time['available_trip_time_minutes'] = df_time.apply(
                    lambda row: (row['requested_dropoff_time'] - row['requested_pickup_time']).total_seconds() / 60
                    if row['has_arrival_constraint'] and pd.notna(row['requested_dropoff_time'])
                    and pd.notna(row['requested_pickup_time'])
                    else None,
                    axis=1
                )

        return df_time

    def sample_for_benchmark(
        self,
        df: pd.DataFrame,
        dev_size: int = 100000,
        val_size: int = 50000,
        test_size: int = 100000,
        time_based_split: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Split data into development, validation, and test sets.

        Args:
            df: Cleaned trip DataFrame
            dev_size: Number of samples for development set
            val_size: Number of samples for validation set
            test_size: Number of samples for test set
            time_based_split: If True, split by time; otherwise random split

        Returns:
            Dictionary with 'dev', 'val', and 'test' DataFrames
        """
        if time_based_split and 'request_datetime' in df.columns:
            # Sort by time
            df_sorted = df.sort_values('request_datetime').reset_index(drop=True)

            # Split sequentially
            dev_end = dev_size
            val_end = dev_end + val_size
            test_end = val_end + test_size

            return {
                'dev': df_sorted.iloc[:dev_end].copy(),
                'val': df_sorted.iloc[dev_end:val_end].copy(),
                'test': df_sorted.iloc[val_end:test_end].copy()
            }
        else:
            # Random split
            df_shuffled = df.sample(frac=1, random_state=42).reset_index(drop=True)

            dev_end = dev_size
            val_end = dev_end + val_size
            test_end = val_end + test_size

            return {
                'dev': df_shuffled.iloc[:dev_end].copy(),
                'val': df_shuffled.iloc[dev_end:val_end].copy(),
                'test': df_shuffled.iloc[val_end:test_end].copy()
            }

    def preprocess_pipeline(
        self,
        parquet_path: str,
        sample_size: Optional[int] = None,
        save_dir: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Complete preprocessing pipeline.

        Args:
            parquet_path: Path to input Parquet file
            sample_size: Optional sample size
            save_dir: Optional directory to save processed data

        Returns:
            Fully preprocessed DataFrame
        """
        print(f"Loading data from {parquet_path}...")
        df = self.load_parquet(parquet_path, sample_size)
        print(f"Loaded {len(df)} records")

        print("Cleaning data...")
        df = self.clean_data(df)
        print(f"After cleaning: {len(df)} records")

        print("Enriching with zone information...")
        df = self.enrich_with_zone_info(df)

        print("Extracting temporal features...")
        df = self.extract_temporal_features(df)

        print("Generating time windows and constraints...")
        df = self.generate_time_windows(df)
        arrival_constraint_pct = (df['has_arrival_constraint'].sum() / len(df)) * 100 if 'has_arrival_constraint' in df.columns else 0
        print(f"  {arrival_constraint_pct:.1f}% of requests have arrival time constraints")

        if save_dir:
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            output_path = Path(save_dir) / 'preprocessed_trips.parquet'
            df.to_parquet(output_path, index=False)
            print(f"Saved preprocessed data to {output_path}")

        return df


def main():
    """Example usage of the preprocessor."""
    # Paths
    taxi_zone_lookup = "/home/hengyu/CS294-Agentic-AI/Agentic-AI/taxi_zone_lookup.csv"
    parquet_file = "/home/hengyu/CS294-Agentic-AI/fhvhv_tripdata_2025-01.parquet"

    # Initialize preprocessor
    preprocessor = NYCTripDataPreprocessor(taxi_zone_lookup)

    # Run preprocessing pipeline (sample 10000 for testing)
    df = preprocessor.preprocess_pipeline(
        parquet_file,
        sample_size=10000,
        save_dir="data/processed"
    )

    print("\nPreprocessed data summary:")
    print(df.head())
    print(f"\nColumns: {df.columns.tolist()}")
    print(f"\nData types:\n{df.dtypes}")

    # Split into benchmark datasets
    print("\nCreating benchmark splits...")
    splits = preprocessor.sample_for_benchmark(df, dev_size=5000, val_size=2500, test_size=2500)
    for split_name, split_df in splits.items():
        print(f"{split_name}: {len(split_df)} records")


if __name__ == "__main__":
    main()
