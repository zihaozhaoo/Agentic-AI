import pandas as pd
import numpy as np
import googlemaps
import sys
import os
import re
import json


def get_google_maps_client():
    """Get Google Maps API client."""
    api_key = "AIzaSyASdmnEivZx-7u6s8tRQn4UbPZ8E9SDe8Y"
    if not api_key:
        print("Missing GOOGLE_MAPS_API_KEY.", file=sys.stderr)
        sys.exit(1)
    return googlemaps.Client(key=api_key)


def parse_location(loc_str):
    """
    Parse location string from CSV format '(lat, lng)' to tuple (lat, lng).
    Returns None if the location is invalid (e.g., contains 'nan').
    """
    if pd.isna(loc_str) or 'nan' in str(loc_str):
        return None

    # Extract numbers from string like "(40.123, -73.456)"
    match = re.match(r'\(([^,]+),\s*([^)]+)\)', loc_str)
    if match:
        lat = float(match.group(1))
        lng = float(match.group(2))
        return (lat, lng)
    return None


def create_node_mapping(csv_file):
    """
    Create node mapping from sampled requests CSV.

    Returns:
    --------
    tuple: (nodes, node_info)
        - nodes: list of (lat, lng) tuples for each node
        - node_info: dict mapping node_id to description

    Node encoding:
        - Node 0: depot (mean lat/lng of all valid locations)
        - Node 2k-1: pickup location of request k (k = 1, 2, ..., n)
        - Node 2k: dropoff location of request k (k = 1, 2, ..., n)
    """
    # Read CSV
    df = pd.read_csv(csv_file)
    print(f"Read {len(df)} requests from {csv_file}")

    # Parse locations
    all_lats = []
    all_lngs = []
    nodes = []
    node_info = {}

    # Reserve node 0 for depot (will calculate later)
    nodes.append(None)
    node_info[0] = "depot"

    # Process each request
    for idx, row in df.iterrows():
        request_num = idx + 1  # 1-indexed request number

        # Parse pickup location
        pickup_loc = parse_location(row['pickup_loc'])
        if pickup_loc:
            all_lats.append(pickup_loc[0])
            all_lngs.append(pickup_loc[1])

        # Parse dropoff location
        dropoff_loc = parse_location(row['dropoff_loc'])
        if dropoff_loc:
            all_lats.append(dropoff_loc[0])
            all_lngs.append(dropoff_loc[1])

        # Assign node IDs
        pickup_node_id = 2 * request_num - 1
        dropoff_node_id = 2 * request_num

        nodes.append(pickup_loc)
        nodes.append(dropoff_loc)

        node_info[pickup_node_id] = f"request_{request_num}_pickup"
        node_info[dropoff_node_id] = f"request_{request_num}_dropoff"

    # Calculate depot location as mean of all valid locations
    if all_lats and all_lngs:
        depot_lat = np.mean(all_lats)
        depot_lng = np.mean(all_lngs)
        nodes[0] = (depot_lat, depot_lng)
        print(f"Depot location: ({depot_lat}, {depot_lng})")
    else:
        print("Error: No valid locations found", file=sys.stderr)
        sys.exit(1)

    print(f"Created {len(nodes)} nodes (including depot)")

    return nodes, node_info


def calculate_distance_matrix(nodes, gmaps_client, batch_size=10):
    """
    Calculate distance matrix using Google Maps Distance Matrix API.

    The API has a limit of 10 origins x 25 destinations per request,
    so we batch the requests.

    Parameters:
    -----------
    nodes : list
        List of (lat, lng) tuples for each node
    gmaps_client : googlemaps.Client
        Google Maps API client
    batch_size : int
        Maximum number of origins/destinations per API call

    Returns:
    --------
    numpy.ndarray
        Travel time matrix in minutes (n x n)
    """
    n = len(nodes)
    distance_matrix = np.zeros((n, n))  # Will store travel times in minutes

    # Convert nodes to strings for API
    locations = []
    for i, node in enumerate(nodes):
        if node is None:
            locations.append(None)
        else:
            locations.append(f"{node[0]},{node[1]}")

    print(f"Calculating travel time matrix for {n} nodes...")
    print("Note: This may take a while due to API rate limits and batching")

    # Process in batches
    for i_start in range(0, n, batch_size):
        i_end = min(i_start + batch_size, n)

        for j_start in range(0, n, batch_size):
            j_end = min(j_start + batch_size, n)

            # Get origins and destinations for this batch
            origins = []
            origin_indices = []
            for i in range(i_start, i_end):
                if locations[i] is not None:
                    origins.append(locations[i])
                    origin_indices.append(i)

            destinations = []
            dest_indices = []
            for j in range(j_start, j_end):
                if locations[j] is not None:
                    destinations.append(locations[j])
                    dest_indices.append(j)

            if not origins or not destinations:
                continue

            print(f"  Batch: origins {i_start}-{i_end-1}, destinations {j_start}-{j_end-1}")

            # Call Distance Matrix API
            result = gmaps_client.distance_matrix(
                origins=origins,
                destinations=destinations,
                mode="driving"
            )

            # Parse results
            if result['status'] == 'OK':
                for orig_idx, i in enumerate(origin_indices):
                    row = result['rows'][orig_idx]
                    for dest_idx, j in enumerate(dest_indices):
                        element = row['elements'][dest_idx]
                        if element['status'] == 'OK':
                            duration = element['duration']['value']  # in seconds
                            distance_matrix[i][j] = duration / 60  # convert to minutes
                        else:
                            # If no route found, set to a large value
                            distance_matrix[i][j] = 999999
                            print(f"    Warning: No route from node {i} to node {j}")
            else:
                print(f"    Error: API returned status {result['status']}", file=sys.stderr)

    print("Travel time matrix calculation complete")

    return distance_matrix


def save_distance_matrix(distance_matrix, nodes, node_info, output_file):
    """
    Save travel time matrix to file.

    Parameters:
    -----------
    distance_matrix : numpy.ndarray
        Travel time matrix (in minutes)
    nodes : list
        List of node locations
    node_info : dict
        Node information mapping
    output_file : str
        Output file path
    """
    # Prepare data to save
    data = {
        'distance_matrix': distance_matrix.tolist(),
        'nodes': [(n[0], n[1]) if n is not None else None for n in nodes],
        'node_info': node_info,
        'num_nodes': len(nodes),
        'units': 'minutes'
    }

    # Save as JSON
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Travel time matrix saved to {output_file}")

    # Also save as numpy array for easy loading
    np_output_file = output_file.replace('.json', '.npy')
    np.save(np_output_file, distance_matrix)
    print(f"Travel time matrix (numpy array) saved to {np_output_file}")


def main():
    """Main function to create travel time matrix from sampled requests."""
    # File paths
    csv_file = "sampled_requests_with_coords.csv"
    output_file = "distance_matrix.json"

    # Check if CSV exists
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found", file=sys.stderr)
        print("Make sure you run this from the src/data_sampling directory", file=sys.stderr)
        sys.exit(1)

    # Create node mapping
    nodes, node_info = create_node_mapping(csv_file)

    # Get Google Maps client
    gmaps_client = get_google_maps_client()

    # Calculate distance matrix
    distance_matrix = calculate_distance_matrix(nodes, gmaps_client)

    # Display sample of travel time matrix
    print("\nSample of travel time matrix (first 5x5 nodes, in minutes):")
    print(distance_matrix[:5, :5])

    # Save results
    save_distance_matrix(distance_matrix, nodes, node_info, output_file)

    print("\nNode encoding:")
    print("  Node 0: depot (mean of all locations)")
    print("  Node 2k-1: pickup location of request k")
    print("  Node 2k: dropoff location of request k")
    print(f"\nTotal nodes: {len(nodes)}")


if __name__ == "__main__":
    main()
