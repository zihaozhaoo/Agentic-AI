import os
import sys
import googlemaps


def get_google_maps_client():
    api_key = None
    if not api_key:
        print("Missing GOOGLE_MAPS_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)
    return googlemaps.Client(key=api_key)


def get_driving_time_text(origin, destination):
    gmaps_client = get_google_maps_client()
    directions = gmaps_client.directions(origin, destination, mode="driving")
    if not directions:
        print("No route found.", file=sys.stderr)
        sys.exit(2)
    leg = directions[0]["legs"][0]
    return leg["duration"]["text"]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python gmap.py \"ORIGIN\" \"DESTINATION\"", file=sys.stderr)
        sys.exit(1)
    origin_arg = sys.argv[1]
    destination_arg = sys.argv[2]
    duration_text = get_driving_time_text(origin_arg, destination_arg)
    print(duration_text)