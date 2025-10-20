import geopandas as gpd
import pandas as pd
import subprocess
import sys


def get_zone_centroids(shapefile_path):
    """
    Load taxi zones shapefile and calculate the centroid (lat, long) for each zone.

    Parameters:
    -----------
    shapefile_path : str
        Path to the taxi zones shapefile

    Returns:
    --------
    pd.DataFrame
        DataFrame with columns: LocationID, latitude, longitude
    """
    print(f"Reading taxi zones from {shapefile_path}...")

    # Read the shapefile
    gdf = gpd.read_file(shapefile_path)

    print(f"Loaded {len(gdf)} taxi zones")
    print(f"Columns: {gdf.columns.tolist()}")

    # Calculate centroids in the original CRS
    gdf['centroid'] = gdf.geometry.centroid

    # Convert to WGS84 (EPSG:4326) for lat/long coordinates
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    centroids_wgs84 = gdf_wgs84.geometry.centroid

    # Extract latitude and longitude
    zone_coords = pd.DataFrame({
        'LocationID': gdf['LocationID'],
        'zone': gdf['zone'],
        'borough': gdf['borough'],
        'latitude': centroids_wgs84.y,
        'longitude': centroids_wgs84.x
    })

    print(f"\nSample of zone centroids:")
    print(zone_coords.head(10))

    return zone_coords


def add_coordinates_to_samples(sampled_requests, zone_coords):
    """
    Add pickup and dropoff coordinates to sampled requests and format for routing.

    Parameters:
    -----------
    sampled_requests : pd.DataFrame
        DataFrame with columns: PULocationID, DOLocationID, lpep_pickup_datetime, lpep_dropoff_datetime
    zone_coords : pd.DataFrame
        DataFrame with columns: LocationID, latitude, longitude

    Returns:
    --------
    pd.DataFrame
        Enhanced DataFrame with columns: pickup_loc, dropoff_loc, pickup_time_window,
        dropoff_time_window, pickup_idx, dropoff_idx
    """
    print("\nAdding coordinates to sampled requests...")

    # Merge pickup coordinates
    result = sampled_requests.merge(
        zone_coords[['LocationID', 'latitude', 'longitude']],
        left_on='PULocationID',
        right_on='LocationID',
        how='left'
    )
    result.rename(columns={'latitude': 'lat_pickup', 'longitude': 'long_pickup'}, inplace=True)
    result.drop(columns=['LocationID'], inplace=True)

    # Merge dropoff coordinates
    result = result.merge(
        zone_coords[['LocationID', 'latitude', 'longitude']],
        left_on='DOLocationID',
        right_on='LocationID',
        how='left'
    )
    result.rename(columns={'latitude': 'lat_dropoff', 'longitude': 'long_dropoff'}, inplace=True)
    result.drop(columns=['LocationID'], inplace=True)

    # Convert datetime columns to pandas datetime
    result['lpep_pickup_datetime'] = pd.to_datetime(result['lpep_pickup_datetime'])
    result['lpep_dropoff_datetime'] = pd.to_datetime(result['lpep_dropoff_datetime'])

    # Create time windows: actual time +/- 5 minutes
    time_delta = pd.Timedelta(minutes=5)

    # Format pickup_time_window as [start, end] timestamps
    result['pickup_time_window'] = result['lpep_pickup_datetime'].apply(
        lambda x: f"[{(x - time_delta).timestamp():.0f}, {(x + time_delta).timestamp():.0f}]"
    )

    # Format dropoff_time_window as [start, end] timestamps
    result['dropoff_time_window'] = result['lpep_dropoff_datetime'].apply(
        lambda x: f"[{(x - time_delta).timestamp():.0f}, {(x + time_delta).timestamp():.0f}]"
    )

    # Create location tuples as strings: (latitude, longitude)
    result['pickup_loc'] = result.apply(
        lambda row: f"({row['lat_pickup']}, {row['long_pickup']})", axis=1
    )
    result['dropoff_loc'] = result.apply(
        lambda row: f"({row['lat_dropoff']}, {row['long_dropoff']})", axis=1
    )

    # Use original location IDs as indices
    result['pickup_idx'] = result['PULocationID']
    result['dropoff_idx'] = result['DOLocationID']

    # Select and reorder final columns
    final_columns = [
        'pickup_loc', 'dropoff_loc',
        'pickup_time_window', 'dropoff_time_window',
        'pickup_idx', 'dropoff_idx'
    ]
    result = result[final_columns]

    print(f"\nProcessed {len(result)} requests with coordinates and time windows")
    print(result.head())

    return result


if __name__ == "__main__":
    # Step 1: Get zone centroids
    shapefile_path = "taxi_zones/taxi_zones.shp"
    zone_coords = get_zone_centroids(shapefile_path)

    # Step 2: Run sample.py to get sampled requests
    print("\n" + "="*60)
    print("Running sample.py to get sampled requests...")
    print("="*60 + "\n")

    # Import and run the sampling function
    sys.path.insert(0, '.')
    from sample import sample_requests

    file_path = "records/green_tripdata_2025-01.parquet"
    sampled_requests = sample_requests(file_path, n_samples=20)

    # Step 3: Add coordinates to sampled requests
    print("\n" + "="*60)
    print("Adding coordinates to sampled requests...")
    print("="*60 + "\n")

    enhanced_requests = add_coordinates_to_samples(sampled_requests, zone_coords)

    # Step 4: Save the result
    output_file = "sampled_requests_with_coords.csv"
    enhanced_requests.to_csv(output_file, index=False)
    print(f"\nEnhanced sampled data saved to {output_file}")

    # Display summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total requests: {len(enhanced_requests)}")
    print(f"\nFirst few requests with coordinates:")
    print(enhanced_requests.to_string())
