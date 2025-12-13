"""
Request Simulation Module

This module provides tools for simulating realistic ride-hailing requests
from structured trip data, including:
- Data preprocessing and cleaning
- Points of Interest (POI) database
- Customer profile generation
- Location augmentation with Google Maps
- Natural language request generation (template-based and LLM-based)
"""

from .data_preprocessing import NYCTripDataPreprocessor
from .poi_database import POIDatabase, POI
from .customer_profiles import CustomerProfileDatabase, CustomerProfile, PersonalPOI
from .location_augmentation import LocationAugmenter, ExactLocation
from .template_generator import TemplateGenerator
from .llm_generator import LLMGenerator
from .request_simulator import RequestSimulator
from .zone_coordinates import (
    get_zone_coordinate,
    get_borough_center,
    get_borough_bounds,
    sample_point_in_borough,
    ZONE_CENTROIDS,
    BOROUGH_LAND_BOUNDS,
    BOROUGH_CENTERS
)

__all__ = [
    'NYCTripDataPreprocessor',
    'POIDatabase',
    'POI',
    'CustomerProfileDatabase',
    'CustomerProfile',
    'PersonalPOI',
    'LocationAugmenter',
    'ExactLocation',
    'TemplateGenerator',
    'LLMGenerator',
    'RequestSimulator',
    # Zone coordinates
    'get_zone_coordinate',
    'get_borough_center',
    'get_borough_bounds',
    'sample_point_in_borough',
    'ZONE_CENTROIDS',
    'BOROUGH_LAND_BOUNDS',
    'BOROUGH_CENTERS'
]

__version__ = '0.1.0'
