"""
Customer Profile Database Module

This module generates synthetic customer profiles with personal POIs
(home, work, favorite places) that can be used in natural language requests.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import random


@dataclass
class PersonalPOI:
    """Personal point of interest for a customer."""
    label: str  # "home", "work", "office", "gym", "favorite restaurant", etc.
    zone_id: int
    zone_name: str
    borough: str
    address: Optional[str] = None


@dataclass
class CustomerProfile:
    """Synthetic customer profile."""
    customer_id: str
    name: str  # Could be used for "my" references
    home: PersonalPOI
    work: Optional[PersonalPOI]
    frequent_locations: List[PersonalPOI]  # gym, favorite bar, parents' house, etc.

    def to_dict(self):
        return {
            'customer_id': self.customer_id,
            'name': self.name,
            'home': asdict(self.home),
            'work': asdict(self.work) if self.work else None,
            'frequent_locations': [asdict(loc) for loc in self.frequent_locations]
        }

    def get_personal_poi_by_label(self, label: str) -> Optional[PersonalPOI]:
        """Get a personal POI by label (case-insensitive)."""
        label_lower = label.lower()

        if 'home' in label_lower or 'house' in label_lower or 'place' in label_lower:
            return self.home

        if self.work and ('work' in label_lower or 'office' in label_lower):
            return self.work

        for loc in self.frequent_locations:
            if label_lower in loc.label.lower():
                return loc

        return None

    def get_random_personal_location(self, exclude_home: bool = False) -> PersonalPOI:
        """Get a random personal location from this customer's profile."""
        locations = []

        if not exclude_home:
            locations.append(self.home)

        if self.work:
            locations.append(self.work)

        locations.extend(self.frequent_locations)

        return random.choice(locations) if locations else self.home


class CustomerProfileDatabase:
    """Database of synthetic customer profiles."""

    def __init__(self, taxi_zone_lookup_path: str):
        """
        Initialize customer profile database.

        Args:
            taxi_zone_lookup_path: Path to taxi zone lookup CSV
        """
        self.zone_lookup = pd.read_csv(taxi_zone_lookup_path)
        self.zone_ids = self.zone_lookup['LocationID'].tolist()
        self.profiles: Dict[str, CustomerProfile] = {}

        # Common personal location labels
        self.frequent_location_labels = [
            "gym",
            "favorite restaurant",
            "favorite bar",
            "parents' house",
            "sister's place",
            "brother's apartment",
            "friend's house",
            "yoga studio",
            "regular coffee shop",
            "favorite brunch spot",
            "doctor's office",
            "salon"
        ]

    def _get_zone_info(self, zone_id: int) -> Dict:
        """Get zone information for a given zone ID."""
        zone_info = self.zone_lookup[self.zone_lookup['LocationID'] == zone_id]
        if zone_info.empty:
            return {'Zone': 'Unknown', 'Borough': 'Unknown'}
        return zone_info.iloc[0].to_dict()

    def _create_personal_poi(self, label: str, zone_id: Optional[int] = None) -> PersonalPOI:
        """Create a personal POI with a random or specified zone."""
        if zone_id is None:
            zone_id = random.choice(self.zone_ids)

        zone_info = self._get_zone_info(zone_id)

        return PersonalPOI(
            label=label,
            zone_id=zone_id,
            zone_name=zone_info['Zone'],
            borough=zone_info['Borough']
        )

    def generate_profile(
        self,
        customer_id: Optional[str] = None,
        home_zone: Optional[int] = None,
        work_zone: Optional[int] = None
    ) -> CustomerProfile:
        """
        Generate a synthetic customer profile.

        Args:
            customer_id: Optional customer ID (auto-generated if None)
            home_zone: Optional specific home zone (random if None)
            work_zone: Optional specific work zone (random if None)

        Returns:
            CustomerProfile object
        """
        if customer_id is None:
            customer_id = f"CUST_{len(self.profiles):06d}"

        # Generate home
        home = self._create_personal_poi("home", home_zone)

        # Generate work (80% of customers have a work location)
        work = None
        if random.random() < 0.8:
            # Work is usually in a different borough or zone
            if work_zone is None:
                work_zone = random.choice([z for z in self.zone_ids if z != home.zone_id])
            work = self._create_personal_poi("work", work_zone)

        # Generate 1-3 frequent locations
        num_frequent = random.randint(1, 3)
        frequent_locations = []

        for _ in range(num_frequent):
            label = random.choice(self.frequent_location_labels)
            # Remove from list to avoid duplicates
            if label in self.frequent_location_labels:
                self.frequent_location_labels.remove(label)
            self.frequent_location_labels.append(label)  # Add back to end

            frequent_locations.append(self._create_personal_poi(label))

        profile = CustomerProfile(
            customer_id=customer_id,
            name=f"Customer_{customer_id}",
            home=home,
            work=work,
            frequent_locations=frequent_locations
        )

        return profile

    def generate_profiles(self, n: int) -> List[CustomerProfile]:
        """
        Generate multiple customer profiles.

        Args:
            n: Number of profiles to generate

        Returns:
            List of CustomerProfile objects
        """
        profiles = []
        for i in range(n):
            profile = self.generate_profile(customer_id=f"CUST_{i:06d}")
            self.profiles[profile.customer_id] = profile
            profiles.append(profile)

        return profiles

    def get_profile(self, customer_id: str) -> Optional[CustomerProfile]:
        """Get a customer profile by ID."""
        return self.profiles.get(customer_id)

    def get_random_profile(self) -> CustomerProfile:
        """Get a random customer profile."""
        return random.choice(list(self.profiles.values()))

    def assign_profile_to_trip(
        self,
        pickup_zone: int,
        dropoff_zone: int,
        probability_personal: float = 0.3
    ) -> Optional[CustomerProfile]:
        """
        Assign a customer profile to a trip based on pickup/dropoff zones.
        Creates a new profile if the zones match common patterns (home/work).

        Args:
            pickup_zone: Pickup zone ID
            dropoff_zone: Dropoff zone ID
            probability_personal: Probability of using a personal location reference

        Returns:
            CustomerProfile if assignment is made, None otherwise
        """
        if random.random() > probability_personal:
            return None

        # Check if we have an existing profile matching these zones
        for profile in self.profiles.values():
            if profile.home.zone_id == pickup_zone:
                return profile
            if profile.work and profile.work.zone_id == pickup_zone:
                return profile

        # Create new profile with these zones
        new_profile = self.generate_profile(
            home_zone=pickup_zone if random.random() < 0.7 else dropoff_zone,
            work_zone=dropoff_zone if random.random() < 0.7 else None
        )
        self.profiles[new_profile.customer_id] = new_profile

        return new_profile

    def save_to_json(self, filepath: str):
        """Save customer profiles to JSON file."""
        data = {
            'profiles': [profile.to_dict() for profile in self.profiles.values()]
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.profiles)} customer profiles to {filepath}")

    def load_from_json(self, filepath: str):
        """Load customer profiles from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        self.profiles = {}
        for profile_dict in data['profiles']:
            home = PersonalPOI(**profile_dict['home'])
            work = PersonalPOI(**profile_dict['work']) if profile_dict['work'] else None
            frequent = [PersonalPOI(**loc) for loc in profile_dict['frequent_locations']]

            profile = CustomerProfile(
                customer_id=profile_dict['customer_id'],
                name=profile_dict['name'],
                home=home,
                work=work,
                frequent_locations=frequent
            )
            self.profiles[profile.customer_id] = profile

        print(f"Loaded {len(self.profiles)} customer profiles from {filepath}")

    def get_statistics(self) -> Dict:
        """Get statistics about the customer profile database."""
        total = len(self.profiles)
        with_work = sum(1 for p in self.profiles.values() if p.work is not None)
        avg_frequent = np.mean([len(p.frequent_locations) for p in self.profiles.values()])

        return {
            'total_customers': total,
            'customers_with_work': with_work,
            'avg_frequent_locations': round(avg_frequent, 2)
        }


def main():
    """Example usage of customer profile database."""
    taxi_zone_lookup = "/home/hengyu/CS294-Agentic-AI/Agentic-AI/taxi_zone_lookup.csv"

    # Create customer profile database
    customer_db = CustomerProfileDatabase(taxi_zone_lookup)

    # Generate some profiles
    print("Generating 100 customer profiles...")
    customer_db.generate_profiles(100)

    # Print statistics
    print("\nCustomer Profile Database Statistics:")
    stats = customer_db.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Example profile
    print("\n\nExample Customer Profile:")
    profile = customer_db.get_random_profile()
    print(f"Customer ID: {profile.customer_id}")
    print(f"Home: {profile.home.zone_name}, {profile.home.borough}")
    if profile.work:
        print(f"Work: {profile.work.zone_name}, {profile.work.borough}")
    print(f"Frequent locations:")
    for loc in profile.frequent_locations:
        print(f"  - {loc.label}: {loc.zone_name}, {loc.borough}")

    # Save to file
    output_dir = Path("data/customers")
    output_dir.mkdir(parents=True, exist_ok=True)
    customer_db.save_to_json(output_dir / "customer_profiles.json")


if __name__ == "__main__":
    main()
