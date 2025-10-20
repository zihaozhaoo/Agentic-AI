"""
Template-based Natural Language Request Generator

This module generates natural language ride requests using template tiers:
1. Basic: Simple origin-destination-time requests
2. POI-based: Using points of interest
3. Time-constrained: Arrival time requirements
4. Multi-stop: Multiple destinations
5. Complex: Accessibility, passengers, luggage, etc.
"""

import random
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class TemplateGenerator:
    """Generates natural language ride requests using templates."""

    def __init__(self):
        """Initialize template generator with template sets."""

        # Template tier probabilities
        self.tier_probabilities = {
            'basic': 0.30,
            'poi_based': 0.25,
            'time_constrained': 0.20,
            'multi_stop': 0.10,
            'complex': 0.15
        }

        # Time format variations
        self.time_formats = [
            lambda dt: dt.strftime('%I:%M %p'),  # "3:30 PM"
            lambda dt: dt.strftime('%I %p'),     # "3 PM"
            lambda dt: dt.strftime('%H:%M'),     # "15:30"
        ]

        # Variations for request phrasing
        self.request_verbs = [
            "I need",
            "I want",
            "I'd like",
            "Can I get",
            "Book me",
            "Get me",
            "I need to book"
        ]

        self.ride_nouns = [
            "a ride",
            "a taxi",
            "a car",
            "an Uber",
            "a Lyft"
        ]

        # Prepositions for origin
        self.origin_preps = [
            "from",
            "at",
            "starting from",
            "pickup at"
        ]

        # Prepositions for destination
        self.dest_preps = [
            "to",
            "headed to",
            "going to",
            "destination"
        ]

    def _format_time(self, dt) -> str:
        """Format datetime in a random natural way."""
        import pandas as pd

        # Handle None or NaT
        if dt is None or (isinstance(dt, type(pd.NaT)) and pd.isna(dt)):
            return "ASAP"

        # Handle pandas Timestamp
        if hasattr(dt, 'to_pydatetime'):
            dt = dt.to_pydatetime()

        formatter = random.choice(self.time_formats)
        return formatter(dt)

    def _get_location_reference(
        self,
        zone_name: str,
        poi_name: Optional[str] = None,
        personal_label: Optional[str] = None,
        address: Optional[str] = None
    ) -> str:
        """
        Get a natural language reference to a location.

        Args:
            zone_name: Taxi zone name
            poi_name: Optional POI name
            personal_label: Optional personal location label (e.g., "home", "work")
            address: Optional street address

        Returns:
            Natural language location reference
        """
        # Priority: personal > address > POI > zone
        # NOTE: Address prioritized over POI because augmented addresses are more accurate
        # than zone-level POIs (which may not match the actual sampled location)

        if personal_label and random.random() < 0.7:
            # Use personal reference
            if 'home' in personal_label.lower():
                return random.choice(["home", "my place", "my house", "my apartment"])
            elif 'work' in personal_label.lower() or 'office' in personal_label.lower():
                return random.choice(["work", "my office", "the office"])
            else:
                return random.choice([personal_label, f"my {personal_label}"])

        # Use address if available (more accurate than zone-level POIs)
        if address and random.random() < 0.7:
            return address

        # Use POI only if no address available
        if poi_name and random.random() < 0.8:
            return poi_name

        return zone_name

    def generate_basic(self, trip_data: Dict[str, Any]) -> str:
        """
        Generate a basic tier request.
        Template: "I need a taxi from Times Square to JFK Airport at 3:30 PM"

        Args:
            trip_data: Dictionary with trip information

        Returns:
            Natural language request
        """
        request_verb = random.choice(self.request_verbs)
        ride_noun = random.choice(self.ride_nouns)
        origin_prep = random.choice(self.origin_preps)
        dest_prep = random.choice(self.dest_preps)

        origin = self._get_location_reference(
            trip_data['pickup_zone'],
            trip_data.get('pickup_poi'),
            trip_data.get('pickup_personal'),
            trip_data.get('pickup_address')
        )

        destination = self._get_location_reference(
            trip_data['dropoff_zone'],
            trip_data.get('dropoff_poi'),
            trip_data.get('dropoff_personal'),
            trip_data.get('dropoff_address')
        )

        # Use requested_pickup_time if available and valid
        import pandas as pd
        pickup_time = trip_data.get('requested_pickup_time')

        # Check for None or NaT
        if pickup_time is None or (hasattr(pd, 'isna') and pd.isna(pickup_time)):
            pickup_time = trip_data.get('request_time')

        # Final fallback
        if pickup_time is None or (hasattr(pd, 'isna') and pd.isna(pickup_time)):
            pickup_time = datetime.now()

        time_str = self._format_time(pickup_time)

        # Add pickup time window if available
        window_str = ""
        if trip_data.get('pickup_window_minutes'):
            window = trip_data['pickup_window_minutes']
            # Sometimes mention the window flexibility
            if random.random() < 0.3:
                window_str = f" (can be ready in {window} minutes)"

        # Optionally include arrival time for some basic requests
        arrival_str = ""
        if trip_data.get('requested_dropoff_time') and random.random() < 0.2:
            arrival_time = trip_data['requested_dropoff_time']
            arrival_str = f", need to arrive by {self._format_time(arrival_time)}"

        templates = [
            f"{request_verb} {ride_noun} {origin_prep} {origin} {dest_prep} {destination} at {time_str}{window_str}{arrival_str}",
            f"{request_verb} {ride_noun} {dest_prep} {destination} {origin_prep} {origin} at {time_str}{window_str}{arrival_str}",
            f"At {time_str}{window_str}, {request_verb.lower()} {ride_noun} {origin_prep} {origin} {dest_prep} {destination}{arrival_str}",
            f"{request_verb} {ride_noun} at {time_str}{window_str} {origin_prep} {origin} {dest_prep} {destination}{arrival_str}"
        ]

        return random.choice(templates)

    def generate_poi_based(self, trip_data: Dict[str, Any]) -> str:
        """
        Generate a POI-based request.
        Template: "Pick me up at Grand Central and take me to the Empire State Building"

        Args:
            trip_data: Dictionary with trip information

        Returns:
            Natural language request
        """
        origin = self._get_location_reference(
            trip_data['pickup_zone'],
            trip_data.get('pickup_poi'),
            trip_data.get('pickup_personal'),
            trip_data.get('pickup_address')
        )

        destination = self._get_location_reference(
            trip_data['dropoff_zone'],
            trip_data.get('dropoff_poi'),
            trip_data.get('dropoff_personal'),
            trip_data.get('dropoff_address')
        )

        templates = [
            f"Pick me up at {origin} and take me to {destination}",
            f"I need to go from {origin} to {destination}",
            f"Take me from {origin} to {destination}",
            f"Can you pick me up at {origin}? I'm going to {destination}",
            f"I'm at {origin} and need to get to {destination}"
        ]

        return random.choice(templates)

    def generate_time_constrained(self, trip_data: Dict[str, Any]) -> str:
        """
        Generate a time-constrained request.
        Template: "I need to arrive at LaGuardia by 5 PM for my flight"

        Args:
            trip_data: Dictionary with trip information

        Returns:
            Natural language request
        """
        origin = self._get_location_reference(
            trip_data['pickup_zone'],
            trip_data.get('pickup_poi'),
            trip_data.get('pickup_personal'),
            trip_data.get('pickup_address')
        )

        destination = self._get_location_reference(
            trip_data['dropoff_zone'],
            trip_data.get('dropoff_poi'),
            trip_data.get('dropoff_personal'),
            trip_data.get('dropoff_address')
        )

        # Use requested_dropoff_time if available and valid
        import pandas as pd
        arrival_time = trip_data.get('requested_dropoff_time')

        # Check for None or NaT
        if arrival_time is None or (hasattr(pd, 'isna') and pd.isna(arrival_time)):
            # Fallback: calculate arrival time (add estimated duration)
            request_time = trip_data.get('request_time')
            if request_time is None or (hasattr(pd, 'isna') and pd.isna(request_time)):
                request_time = datetime.now()

            arrival_time = request_time + timedelta(
                minutes=trip_data.get('estimated_duration_minutes', 30)
            )

        arrival_str = self._format_time(arrival_time)

        # Add time window if available
        time_window_str = ""
        if trip_data.get('dropoff_window_minutes'):
            window = trip_data['dropoff_window_minutes']
            time_window_options = [
                "",
                f" (±{window} minutes)",
                f", give or take {window} minutes",
            ]
            time_window_str = random.choice(time_window_options)

        # Reason depends on time of day and destination
        reasons = [
            "for my flight",
            "for a meeting",
            "for an appointment",
            "for work",
            "for dinner",
            "to catch my train",
            "for a class",
            ""
        ]

        reason = random.choice(reasons)

        # Add urgency for tight constraints
        urgency_prefix = ""
        if trip_data.get('is_tight_constraint'):
            urgency_options = [
                "",
                "It's urgent - ",
                "This is time-sensitive - ",
                "I'm running late - ",
            ]
            urgency_prefix = random.choice(urgency_options)

        templates = [
            f"{urgency_prefix}I need to arrive at {destination} by {arrival_str}{time_window_str} {reason}".strip(),
            f"{urgency_prefix}I need to be at {destination} by {arrival_str}{time_window_str} {reason}".strip(),
            f"Pick me up from {origin}, {urgency_prefix.lower()}I have to be at {destination} by {arrival_str}{time_window_str} {reason}".strip(),
            f"I need a ride from {origin} to {destination}, must arrive by {arrival_str}{time_window_str} {reason}".strip(),
            f"Can you get me to {destination} by {arrival_str}{time_window_str}? Picking up from {origin}. {reason.capitalize() if reason else ''}".strip()
        ]

        return random.choice(templates)

    def generate_multi_stop(self, trip_data: Dict[str, Any]) -> str:
        """
        Generate a multi-stop request.
        Template: "Pick me up at Penn Station, stop at Brooklyn, then to JFK"

        Args:
            trip_data: Dictionary with trip information

        Returns:
            Natural language request
        """
        origin = self._get_location_reference(
            trip_data['pickup_zone'],
            trip_data.get('pickup_poi'),
            trip_data.get('pickup_personal'),
            trip_data.get('pickup_address')
        )

        destination = self._get_location_reference(
            trip_data['dropoff_zone'],
            trip_data.get('dropoff_poi'),
            trip_data.get('dropoff_personal'),
            trip_data.get('dropoff_address')
        )

        # Generate a random intermediate stop (use borough or nearby zone)
        intermediate_stops = trip_data.get('intermediate_stops', [])

        if not intermediate_stops:
            # Create a synthetic intermediate stop
            intermediate = random.choice([
                "Brooklyn",
                "Queens",
                "the Upper East Side",
                "Midtown",
                "Downtown"
            ])
        else:
            intermediate = random.choice(intermediate_stops)

        templates = [
            f"Pick me up at {origin}, stop at {intermediate}, then to {destination}",
            f"I need a ride from {origin} to {destination} with a stop at {intermediate}",
            f"From {origin}, first stop at {intermediate}, final destination {destination}",
            f"Can you take me from {origin} to {destination}? I need to stop at {intermediate} on the way"
        ]

        return random.choice(templates)

    def generate_complex(self, trip_data: Dict[str, Any]) -> str:
        """
        Generate a complex request with accessibility, passengers, luggage, etc.
        Template: "Wheelchair-accessible vehicle from 57th St to JFK Terminal 4,
                   2 passengers, 3 bags, arrive by 5 PM"

        Args:
            trip_data: Dictionary with trip information

        Returns:
            Natural language request
        """
        origin = self._get_location_reference(
            trip_data['pickup_zone'],
            trip_data.get('pickup_poi'),
            trip_data.get('pickup_personal'),
            trip_data.get('pickup_address')
        )

        destination = self._get_location_reference(
            trip_data['dropoff_zone'],
            trip_data.get('dropoff_poi'),
            trip_data.get('dropoff_personal'),
            trip_data.get('dropoff_address')
        )

        # Collect complex requirements
        requirements = []

        # Accessibility
        if trip_data.get('wav_request_flag') == 'Y' or random.random() < 0.1:
            requirements.append(random.choice([
                "Wheelchair-accessible vehicle",
                "WAV required",
                "Need wheelchair access",
                "Accessible vehicle"
            ]))

        # Passengers
        num_passengers = trip_data.get('passenger_count', random.randint(1, 4))
        if num_passengers > 1:
            requirements.append(f"{num_passengers} passengers")

        # Luggage
        if random.random() < 0.3:
            num_bags = random.randint(1, 5)
            requirements.append(f"{num_bags} {'bag' if num_bags == 1 else 'bags'}")

        # Shared ride preference
        if trip_data.get('shared_request_flag') == 'Y' or random.random() < 0.1:
            requirements.append(random.choice([
                "shared ride OK",
                "pooled ride",
                "UberPool",
                "willing to share"
            ]))

        # Time constraint
        if random.random() < 0.5:
            arrival_time = trip_data['request_time'] + timedelta(
                minutes=trip_data.get('estimated_duration_minutes', 30)
            )
            requirements.append(f"arrive by {self._format_time(arrival_time)}")

        # Build the request
        if requirements:
            req_str = ", ".join(requirements)
            templates = [
                f"{req_str} from {origin} to {destination}",
                f"I need a ride from {origin} to {destination}. {req_str}",
                f"From {origin} to {destination}, {req_str}",
                f"Book me a ride: {origin} to {destination}, {req_str}"
            ]
        else:
            # Fallback to basic if no special requirements
            return self.generate_basic(trip_data)

        return random.choice(templates)

    def generate(self, trip_data: Dict[str, Any], tier: Optional[str] = None) -> Dict[str, str]:
        """
        Generate a natural language request.

        Args:
            trip_data: Dictionary with trip information
            tier: Optional specific tier to use (None = random based on probabilities)

        Returns:
            Dictionary with 'tier' and 'request' keys
        """
        if tier is None:
            # Select tier based on probabilities
            tier = random.choices(
                list(self.tier_probabilities.keys()),
                weights=list(self.tier_probabilities.values())
            )[0]

        # Generate request based on tier
        generators = {
            'basic': self.generate_basic,
            'poi_based': self.generate_poi_based,
            'time_constrained': self.generate_time_constrained,
            'multi_stop': self.generate_multi_stop,
            'complex': self.generate_complex
        }

        generator = generators.get(tier, self.generate_basic)
        request_text = generator(trip_data)

        return {
            'tier': tier,
            'request': request_text,
            'generation_method': 'template'
        }


def main():
    """Example usage of template generator."""
    from datetime import datetime

    generator = TemplateGenerator()

    # Example trip data
    trip_data = {
        'pickup_zone': 'Upper East Side',
        'dropoff_zone': 'JFK Airport',
        'pickup_poi': 'Central Park',
        'dropoff_poi': 'JFK',
        'request_time': datetime(2025, 1, 15, 14, 30),
        'estimated_duration_minutes': 45,
        'passenger_count': 2,
        'wav_request_flag': 'N',
        'shared_request_flag': 'N'
    }

    print("Template-based Natural Language Request Examples:\n")

    # Generate one of each tier
    for tier in ['basic', 'poi_based', 'time_constrained', 'multi_stop', 'complex']:
        result = generator.generate(trip_data, tier=tier)
        print(f"{tier.upper()}: {result['request']}\n")

    print("\n--- Random Tier Examples ---\n")
    for i in range(5):
        result = generator.generate(trip_data)
        print(f"[{result['tier']}] {result['request']}\n")


if __name__ == "__main__":
    main()
