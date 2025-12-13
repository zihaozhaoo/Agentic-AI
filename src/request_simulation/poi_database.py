"""
Points of Interest (POI) Database Module

This module creates and manages a database of important locations in NYC
that can be referenced in natural language ride requests.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import random


@dataclass
class POI:
    """Point of Interest data structure."""
    name: str
    category: str  # airport, landmark, transit, business, entertainment, etc.
    zone_id: int
    zone_name: str
    borough: str
    alternative_names: List[str]  # Alternative ways to refer to this POI
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class POIDatabase:
    """Database of Points of Interest in NYC."""

    def __init__(self, taxi_zone_lookup_path: str):
        """
        Initialize POI database.

        Args:
            taxi_zone_lookup_path: Path to taxi zone lookup CSV
        """
        self.zone_lookup = pd.read_csv(taxi_zone_lookup_path)
        self.pois: List[POI] = []
        self._create_default_pois()

    def _create_default_pois(self):
        """Create a default set of well-known NYC POIs."""

        # Airports
        self.add_poi(POI(
            name="JFK Airport",
            category="airport",
            zone_id=132,
            zone_name="JFK Airport",
            borough="Queens",
            alternative_names=["JFK", "Kennedy Airport", "John F. Kennedy Airport", "JFK International"]
        ))

        self.add_poi(POI(
            name="LaGuardia Airport",
            category="airport",
            zone_id=138,
            zone_name="LaGuardia Airport",
            borough="Queens",
            alternative_names=["LGA", "LaGuardia", "La Guardia"]
        ))

        self.add_poi(POI(
            name="Newark Airport",
            category="airport",
            zone_id=1,
            zone_name="Newark Airport",
            borough="EWR",
            alternative_names=["EWR", "Newark Liberty", "Newark Liberty International"]
        ))

        # Major Transit Hubs
        self.add_poi(POI(
            name="Penn Station",
            category="transit",
            zone_id=186,
            zone_name="Penn Station/Madison Sq West",
            borough="Manhattan",
            alternative_names=["Pennsylvania Station", "Penn", "Madison Square Garden area"]
        ))

        self.add_poi(POI(
            name="Grand Central Terminal",
            category="transit",
            zone_id=162,
            zone_name="Midtown East",
            borough="Manhattan",
            alternative_names=["Grand Central", "Grand Central Station", "GCT"]
        ))

        # Landmarks
        self.add_poi(POI(
            name="Times Square",
            category="landmark",
            zone_id=230,
            zone_name="Times Sq/Theatre District",
            borough="Manhattan",
            alternative_names=["Times Sq", "Theatre District", "Broadway area"]
        ))

        self.add_poi(POI(
            name="Empire State Building",
            category="landmark",
            zone_id=170,
            zone_name="Murray Hill",
            borough="Manhattan",
            alternative_names=["Empire State", "ESB"]
        ))

        self.add_poi(POI(
            name="Central Park",
            category="landmark",
            zone_id=43,
            zone_name="Central Park",
            borough="Manhattan",
            alternative_names=["the park", "CP"]
        ))

        self.add_poi(POI(
            name="Statue of Liberty",
            category="landmark",
            zone_id=103,
            zone_name="Governor's Island/Ellis Island/Liberty Island",
            borough="Manhattan",
            alternative_names=["Liberty Island", "Lady Liberty"]
        ))

        # Business Districts
        self.add_poi(POI(
            name="Wall Street",
            category="business",
            zone_id=87,
            zone_name="Financial District North",
            borough="Manhattan",
            alternative_names=["Financial District", "FiDi", "Downtown Manhattan"]
        ))

        self.add_poi(POI(
            name="World Trade Center",
            category="business",
            zone_id=261,
            zone_name="World Trade Center",
            borough="Manhattan",
            alternative_names=["WTC", "One World Trade", "Freedom Tower"]
        ))

        # Entertainment & Culture
        self.add_poi(POI(
            name="Brooklyn Bridge",
            category="landmark",
            zone_id=231,
            zone_name="TriBeCa/Civic Center",
            borough="Manhattan",
            alternative_names=["the bridge to Brooklyn"]
        ))

        self.add_poi(POI(
            name="Madison Square Garden",
            category="entertainment",
            zone_id=186,
            zone_name="Penn Station/Madison Sq West",
            borough="Manhattan",
            alternative_names=["MSG", "The Garden"]
        ))

        # Neighborhoods
        self.add_poi(POI(
            name="SoHo",
            category="neighborhood",
            zone_id=211,
            zone_name="SoHo",
            borough="Manhattan",
            alternative_names=["South of Houston"]
        ))

        self.add_poi(POI(
            name="Williamsburg",
            category="neighborhood",
            zone_id=255,
            zone_name="Williamsburg (North Side)",
            borough="Brooklyn",
            alternative_names=["North Williamsburg", "Northside Williamsburg"]
        ))

        self.add_poi(POI(
            name="Chinatown",
            category="neighborhood",
            zone_id=45,
            zone_name="Chinatown",
            borough="Manhattan",
            alternative_names=["Manhattan Chinatown"]
        ))

        # Shopping
        self.add_poi(POI(
            name="Macy's Herald Square",
            category="shopping",
            zone_id=161,
            zone_name="Midtown Center",
            borough="Manhattan",
            alternative_names=["Macy's", "Herald Square"]
        ))

        # Universities
        self.add_poi(POI(
            name="Columbia University",
            category="university",
            zone_id=166,
            zone_name="Morningside Heights",
            borough="Manhattan",
            alternative_names=["Columbia", "Columbia U"]
        ))

    def add_poi(self, poi: POI):
        """Add a POI to the database."""
        self.pois.append(poi)

    def get_poi_by_name(self, name: str) -> Optional[POI]:
        """Get POI by exact name match."""
        for poi in self.pois:
            if poi.name.lower() == name.lower():
                return poi
            if any(alt.lower() == name.lower() for alt in poi.alternative_names):
                return poi
        return None

    def get_pois_by_category(self, category: str) -> List[POI]:
        """Get all POIs in a specific category."""
        return [poi for poi in self.pois if poi.category == category]

    def get_pois_by_zone(self, zone_id: int) -> List[POI]:
        """Get all POIs in a specific taxi zone."""
        return [poi for poi in self.pois if poi.zone_id == zone_id]

    def get_random_poi(self, category: Optional[str] = None) -> POI:
        """Get a random POI, optionally filtered by category."""
        if category:
            filtered_pois = self.get_pois_by_category(category)
            return random.choice(filtered_pois) if filtered_pois else random.choice(self.pois)
        return random.choice(self.pois)

    def sample_pois_for_zone(self, zone_id: int, n: int = 3) -> List[str]:
        """
        Sample POI names that could be used for a given zone.
        Returns a mix of exact matches and nearby/borough-level POIs.

        Args:
            zone_id: Taxi zone ID
            n: Number of POI references to generate

        Returns:
            List of POI name variations
        """
        zone_info = self.zone_lookup[self.zone_lookup['LocationID'] == zone_id]
        if zone_info.empty:
            return []

        zone_name = zone_info.iloc[0]['Zone']
        borough = zone_info.iloc[0]['Borough']

        # Check for exact POI matches in this zone
        exact_pois = self.get_pois_by_zone(zone_id)

        # Get POIs in the same borough
        borough_pois = [poi for poi in self.pois if poi.borough == borough]

        result = []

        # Add exact matches first
        if exact_pois:
            result.extend([random.choice([poi.name] + poi.alternative_names) for poi in exact_pois[:n]])

        # Fill remaining with zone name or borough POIs
        while len(result) < n:
            if random.random() < 0.7:  # 70% chance to use actual zone name
                result.append(zone_name)
            elif borough_pois:  # 30% chance to use a borough POI
                poi = random.choice(borough_pois)
                result.append(random.choice([poi.name] + poi.alternative_names))
            else:
                result.append(zone_name)

        return result[:n]

    def save_to_json(self, filepath: str):
        """Save POI database to JSON file."""
        data = {
            'pois': [poi.to_dict() for poi in self.pois]
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.pois)} POIs to {filepath}")

    def load_from_json(self, filepath: str):
        """Load POI database from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        self.pois = []
        for poi_dict in data['pois']:
            self.pois.append(POI(**poi_dict))

        print(f"Loaded {len(self.pois)} POIs from {filepath}")

    def get_statistics(self) -> Dict:
        """Get statistics about the POI database."""
        categories = {}
        boroughs = {}

        for poi in self.pois:
            categories[poi.category] = categories.get(poi.category, 0) + 1
            boroughs[poi.borough] = boroughs.get(poi.borough, 0) + 1

        return {
            'total_pois': len(self.pois),
            'categories': categories,
            'boroughs': boroughs
        }


def main():
    """Example usage of POI database."""
    taxi_zone_lookup = "/home/hengyu/CS294-Agentic-AI/Agentic-AI/taxi_zone_lookup.csv"

    # Create POI database
    poi_db = POIDatabase(taxi_zone_lookup)

    # Print statistics
    print("POI Database Statistics:")
    stats = poi_db.get_statistics()
    print(f"Total POIs: {stats['total_pois']}")
    print(f"\nBy Category:")
    for category, count in stats['categories'].items():
        print(f"  {category}: {count}")
    print(f"\nBy Borough:")
    for borough, count in stats['boroughs'].items():
        print(f"  {borough}: {count}")

    # Example queries
    print("\n\nExample Queries:")
    print(f"Airports: {[poi.name for poi in poi_db.get_pois_by_category('airport')]}")
    print(f"Random POI: {poi_db.get_random_poi().name}")

    # Save to file
    output_dir = Path("data/poi")
    output_dir.mkdir(parents=True, exist_ok=True)
    poi_db.save_to_json(output_dir / "poi_database.json")


if __name__ == "__main__":
    main()
