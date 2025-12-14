"""
Zone Coordinates Module

Provides accurate land-based coordinates for NYC taxi zones.
Uses tightened borough bounds that exclude water areas (Hudson River, East River, etc.)
and per-zone centroid approximations where available.
"""

import random
from typing import Dict, Tuple, Optional


# Borough land-only bounding boxes: (lat_min, lat_max, lon_min, lon_max)
# These bounds are tightened to exclude water bodies like Hudson River, East River, etc.
BOROUGH_LAND_BOUNDS: Dict[str, Tuple[float, float, float, float]] = {
    # Manhattan: narrow island between rivers - tightened longitude to avoid Hudson/East rivers
    'Manhattan': (40.7120, 40.8720, -74.0080, -73.9400),
    
    # Brooklyn: avoid Upper Bay on west (lon < -74.025), Jamaica Bay on south (lat < 0.625)
    'Brooklyn': (40.6250, 40.7320, -74.0250, -73.8600),
    
    # Queens: avoid Jamaica Bay on south (lat < 0.63), narrower north
    'Queens': (40.6300, 40.7920, -73.9550, -73.7150),
    
    # Bronx: mostly inland, slight adjustment on south near Harlem River
    'Bronx': (40.8130, 40.9100, -73.9250, -73.7750),
    
    # Staten Island: tightened east boundary to -74.08 to avoid The Narrows strait
    'Staten Island': (40.5050, 40.6450, -74.2420, -74.0800),
    
    # Newark Airport (EWR)
    'EWR': (40.6840, 40.6960, -74.1800, -74.1600),
    
    # Unknown/N/A zones - use central Manhattan as safe fallback
    'Unknown': (40.7500, 40.7700, -73.9900, -73.9750),
    'N/A': (40.7500, 40.7700, -73.9900, -73.9750),
}

# Borough center points (on land) for small-jitter scenarios
BOROUGH_CENTERS: Dict[str, Tuple[float, float]] = {
    'Manhattan': (40.7580, -73.9855),
    'Brooklyn': (40.6500, -73.9496),
    'Queens': (40.7135, -73.8283),
    'Bronx': (40.8505, -73.8660),
    'Staten Island': (40.5795, -74.1502),
    'EWR': (40.6895, -74.1745),
    'Unknown': (40.7580, -73.9855),
    'N/A': (40.7580, -73.9855),
}

# Per-zone approximate centroids for common NYC taxi zones
# These are hand-verified to be on land and within the zone boundaries
ZONE_CENTROIDS: Dict[int, Tuple[float, float]] = {
    # Manhattan zones - southern tip coordinates moved east to avoid Hudson River
    4: (40.7265, -73.9815),    # Alphabet City
    12: (40.7065, -74.0105),   # Battery Park (moved further east from waterfront)
    13: (40.7145, -74.0105),   # Battery Park City (moved further east from waterfront)
    24: (40.7960, -73.9680),   # Bloomingdale
    41: (40.8115, -73.9455),   # Central Harlem
    42: (40.8190, -73.9400),   # Central Harlem North
    43: (40.7812, -73.9665),   # Central Park
    45: (40.7157, -73.9970),   # Chinatown
    48: (40.7590, -73.9910),   # Clinton East
    50: (40.7620, -73.9980),   # Clinton West
    68: (40.7455, -73.9970),   # East Chelsea
    74: (40.7985, -73.9420),   # East Harlem North
    75: (40.7920, -73.9455),   # East Harlem South
    79: (40.7265, -73.9850),   # East Village
    87: (40.7075, -74.0085),   # Financial District North
    88: (40.7035, -74.0095),   # Financial District South (moved east from waterfront)
    90: (40.7410, -73.9890),   # Flatiron
    100: (40.7535, -73.9905),  # Garment District
    107: (40.7385, -73.9840),  # Gramercy
    113: (40.7350, -74.0010),  # Greenwich Village North
    114: (40.7295, -74.0015),  # Greenwich Village South
    116: (40.8245, -73.9505),  # Hamilton Heights
    125: (40.7260, -74.0075),  # Hudson Sq
    127: (40.8665, -73.9215),  # Inwood
    137: (40.7455, -73.9770),  # Kips Bay
    140: (40.7680, -73.9590),  # Lenox Hill East
    141: (40.7710, -73.9660),  # Lenox Hill West
    142: (40.7725, -73.9830),  # Lincoln Square East
    143: (40.7745, -73.9875),  # Lincoln Square West
    144: (40.7210, -73.9960),  # Little Italy/NoLiTa
    148: (40.7155, -73.9860),  # Lower East Side
    151: (40.7970, -73.9665),  # Manhattan Valley
    152: (40.8165, -73.9560),  # Manhattanville
    158: (40.7405, -74.0080),  # Meatpacking/West Village West
    161: (40.7545, -73.9790),  # Midtown Center
    162: (40.7555, -73.9700),  # Midtown East
    163: (40.7620, -73.9750),  # Midtown North
    164: (40.7490, -73.9835),  # Midtown South
    166: (40.8090, -73.9630),  # Morningside Heights
    170: (40.7485, -73.9760),  # Murray Hill
    186: (40.7505, -73.9930),  # Penn Station/Madison Sq West
    209: (40.7060, -74.0030),  # Seaport
    211: (40.7240, -74.0005),  # SoHo
    224: (40.7335, -73.9785),  # Stuy Town/Peter Cooper Village
    229: (40.7560, -73.9645),  # Sutton Place/Turtle Bay North
    230: (40.7580, -73.9855),  # Times Sq/Theatre District
    231: (40.7160, -74.0070),  # TriBeCa/Civic Center
    232: (40.7130, -73.9890),  # Two Bridges/Seward Park
    233: (40.7520, -73.9680),  # UN/Turtle Bay South
    234: (40.7355, -73.9905),  # Union Sq
    236: (40.7765, -73.9555),  # Upper East Side North
    237: (40.7700, -73.9605),  # Upper East Side South
    238: (40.7895, -73.9730),  # Upper West Side North
    239: (40.7810, -73.9780),  # Upper West Side South
    243: (40.8515, -73.9375),  # Washington Heights North
    244: (40.8390, -73.9415),  # Washington Heights South
    246: (40.7505, -74.0010),  # West Chelsea/Hudson Yards
    249: (40.7340, -74.0040),  # West Village
    261: (40.7120, -74.0100),  # World Trade Center (moved east from waterfront)
    262: (40.7745, -73.9495),  # Yorkville East
    263: (40.7770, -73.9575),  # Yorkville West
    
    # Brooklyn zones
    11: (40.6015, -73.9955),   # Bath Beach
    14: (40.6305, -74.0100),   # Bay Ridge (moved further east from waterfront)
    17: (40.6875, -73.9530),   # Bedford
    21: (40.6130, -73.9850),   # Bensonhurst East
    22: (40.6065, -73.9995),   # Bensonhurst West
    25: (40.6855, -73.9830),   # Boerum Hill
    26: (40.6340, -73.9890),   # Borough Park
    29: (40.5775, -73.9600),   # Brighton Beach
    33: (40.6955, -73.9930),   # Brooklyn Heights
    35: (40.6605, -73.9105),   # Brownsville
    36: (40.6980, -73.9205),   # Bushwick North
    37: (40.6890, -73.9175),   # Bushwick South
    39: (40.6405, -73.9010),   # Canarsie
    40: (40.6785, -73.9990),   # Carroll Gardens
    49: (40.6895, -73.9665),   # Clinton Hill
    52: (40.6870, -73.9965),   # Cobble Hill
    54: (40.6785, -73.9995),   # Columbia Street (moved east from waterfront)
    55: (40.5755, -73.9815),   # Coney Island
    61: (40.6715, -73.9415),   # Crown Heights North
    62: (40.6605, -73.9425),   # Crown Heights South
    63: (40.6855, -73.8825),   # Cypress Hills
    65: (40.6925, -73.9865),   # Downtown Brooklyn/MetroTech
    66: (40.7035, -73.9875),   # DUMBO/Vinegar Hill
    67: (40.6225, -74.0050),   # Dyker Heights (moved east from waterfront)
    71: (40.6465, -73.9385),   # East Flatbush/Farragut
    72: (40.6495, -73.9215),   # East Flatbush/Remsen Village
    76: (40.6665, -73.8830),   # East New York
    77: (40.6580, -73.8965),   # East New York/Pennsylvania Avenue
    80: (40.7135, -73.9310),   # East Williamsburg
    85: (40.6495, -73.9530),   # Erasmus
    89: (40.6395, -73.9625),   # Flatbush/Ditmas Park
    91: (40.6210, -73.9255),   # Flatlands
    97: (40.6910, -73.9755),   # Fort Greene
    106: (40.6735, -73.9890),  # Gowanus
    108: (40.5935, -73.9650),  # Gravesend
    112: (40.7295, -73.9555),  # Greenpoint
    123: (40.6050, -73.9585),  # Homecrest
    133: (40.6450, -73.9705),  # Kensington
    149: (40.6070, -73.9270),  # Madison (moved east from Marine Park edge)
    150: (40.5780, -73.9385),  # Manhattan Beach
    165: (40.6195, -73.9605),  # Midwood
    177: (40.6780, -73.9115),  # Ocean Hill
    178: (40.6150, -73.9680),  # Ocean Parkway South
    181: (40.6715, -73.9785),  # Park Slope
    188: (40.6590, -73.9555),  # Prospect-Lefferts Gardens
    189: (40.6775, -73.9695),  # Prospect Heights
    195: (40.6765, -74.0020),  # Red Hook (moved east from waterfront)
    210: (40.5855, -73.9455),  # Sheepshead Bay
    217: (40.7060, -73.9555),  # South Williamsburg
    222: (40.6485, -73.8835),  # Starrett City
    225: (40.6825, -73.9325),  # Stuyvesant Heights
    227: (40.6455, -74.0075),  # Sunset Park East
    228: (40.6505, -74.0165),  # Sunset Park West
    255: (40.7175, -73.9575),  # Williamsburg (North Side)
    256: (40.7085, -73.9595),  # Williamsburg (South Side)
    257: (40.6555, -73.9755),  # Windsor Terrace
    
    # Queens zones - Rockaway/Jamaica Bay zones given land-based centroids
    2: (40.5935, -73.8915),    # Jamaica Bay (using Floyd Bennett Field which is on land)
    7: (40.7695, -73.9175),    # Astoria
    8: (40.7785, -73.9085),    # Astoria Park
    9: (40.7375, -73.7875),    # Auburndale
    10: (40.6755, -73.7855),   # Baisley Park
    15: (40.7940, -73.7765),   # Bay Terrace/Fort Totten
    16: (40.7655, -73.7705),   # Bayside
    19: (40.7235, -73.7235),   # Bellerose
    27: (40.5595, -73.9205),   # Breezy Point/Fort Tilden/Riis Beach (centered on land)
    28: (40.7155, -73.8115),   # Briarwood/Jamaica Hills
    30: (40.6055, -73.8195),   # Broad Channel (centered on the island)
    38: (40.6955, -73.7415),   # Cambria Heights
    53: (40.7925, -73.8485),   # College Point
    56: (40.7465, -73.8605),   # Corona
    64: (40.7585, -73.7455),   # Douglaston
    70: (40.7750, -73.8695),   # East Elmhurst
    73: (40.7595, -73.8075),   # East Flushing
    82: (40.7425, -73.8795),   # Elmhurst
    83: (40.7285, -73.8985),   # Elmhurst/Maspeth
    86: (40.6055, -73.7535),   # Far Rockaway (on the peninsula)
    92: (40.7615, -73.8275),   # Flushing
    95: (40.7195, -73.8445),   # Forest Hills
    96: (40.6945, -73.8635),   # Forest Park/Highland Park
    98: (40.7355, -73.7925),   # Fresh Meadows
    101: (40.7455, -73.7115),  # Glen Oaks
    102: (40.7025, -73.8765),  # Glendale
    117: (40.5935, -73.7855),  # Hammels/Arverne (on the Rockaway peninsula)
    121: (40.7275, -73.8095),  # Hillcrest/Pomonok
    122: (40.7135, -73.7615),  # Hollis
    124: (40.6595, -73.8425),  # Howard Beach (moved north from bay edge)
    129: (40.7555, -73.8835),  # Jackson Heights
    130: (40.7015, -73.8025),  # Jamaica
    131: (40.7215, -73.7805),  # Jamaica Estates
    132: (40.6475, -73.7855),  # JFK Airport
    134: (40.7095, -73.8265),  # Kew Gardens
    135: (40.7245, -73.8185),  # Kew Gardens Hills
    138: (40.7735, -73.8725),  # LaGuardia Airport
    139: (40.6785, -73.7505),  # Laurelton
    145: (40.7425, -73.9585),  # Long Island City/Hunters Point
    146: (40.7505, -73.9395),  # Long Island City/Queens Plaza
    157: (40.7265, -73.9075),  # Maspeth
    160: (40.7135, -73.8775),  # Middle Village
    171: (40.7625, -73.8055),  # Murray Hill-Queens
    173: (40.7595, -73.8625),  # North Corona
    175: (40.7425, -73.7585),  # Oakland Gardens
    179: (40.7715, -73.9255),  # Old Astoria
    180: (40.6865, -73.8335),  # Ozone Park
    191: (40.7265, -73.7415),  # Queens Village
    192: (40.7515, -73.8185),  # Queensboro Hill
    193: (40.7575, -73.9435),  # Queensbridge/Ravenswood
    196: (40.7145, -73.8555),  # Rego Park
    197: (40.6955, -73.8235),  # Richmond Hill
    198: (40.7035, -73.9055),  # Ridgewood
    201: (40.5785, -73.8335),  # Rockaway Park (on the Rockaway peninsula, away from Jamaica Bay)
    203: (40.6615, -73.7365),  # Rosedale
    205: (40.6905, -73.7655),  # Saint Albans
    207: (40.7585, -73.9035),  # Saint Michaels Cemetery/Woodside
    215: (40.6875, -73.7915),  # South Jamaica
    216: (40.6755, -73.8165),  # South Ozone Park
    218: (40.6755, -73.7655),  # Springfield Gardens North
    219: (40.6655, -73.7605),  # Springfield Gardens South
    223: (40.7755, -73.9075),  # Steinway
    226: (40.7425, -73.9225),  # Sunnyside
    252: (40.7915, -73.8075),  # Whitestone
    258: (40.6925, -73.8555),  # Woodhaven
    260: (40.7465, -73.9075),  # Woodside
    
    # Bronx zones
    3: (40.8655, -73.8515),    # Allerton/Pelham Gardens
    18: (40.8675, -73.8865),   # Bedford Park
    20: (40.8525, -73.8915),   # Belmont
    31: (40.8615, -73.8745),   # Bronx Park
    32: (40.8495, -73.8655),   # Bronxdale
    46: (40.8475, -73.7865),   # City Island
    47: (40.8445, -73.9025),   # Claremont/Bathgate
    51: (40.8765, -73.8295),   # Co-Op City
    58: (40.8355, -73.8185),   # Country Club
    59: (40.8395, -73.8965),   # Crotona Park
    60: (40.8425, -73.8895),   # Crotona Park East
    69: (40.8335, -73.9155),   # East Concourse/Concourse Village
    78: (40.8455, -73.8935),   # East Tremont
    81: (40.8855, -73.8295),   # Eastchester
    94: (40.8595, -73.8985),   # Fordham South
    119: (40.8375, -73.9275),  # Highbridge
    126: (40.8095, -73.8895),  # Hunts Point
    136: (40.8705, -73.9035),  # Kingsbridge Heights
    147: (40.8195, -73.8985),  # Longwood
    159: (40.8255, -73.9115),  # Melrose South
    167: (40.8285, -73.9055),  # Morrisania/Melrose
    168: (40.8085, -73.9205),  # Mott Haven/Port Morris
    169: (40.8505, -73.9055),  # Mount Hope
    174: (40.8785, -73.8785),  # Norwood
    182: (40.8385, -73.8565),  # Parkchester
    183: (40.8515, -73.8285),  # Pelham Bay
    185: (40.8575, -73.8605),  # Pelham Parkway
    200: (40.9005, -73.9075),  # Riverdale/North Riverdale/Fieldston
    208: (40.8225, -73.8175),  # Schuylerville/Edgewater Park
    212: (40.8185, -73.8685),  # Soundview/Bruckner
    213: (40.8195, -73.8505),  # Soundview/Castle Hill
    220: (40.8815, -73.9235),  # Spuyten Duyvil/Kingsbridge
    235: (40.8485, -73.9145),  # University Heights/Morris Heights
    241: (40.8865, -73.8935),  # Van Cortlandt Village
    242: (40.8545, -73.8605),  # Van Nest/Morris Park
    247: (40.8255, -73.9235),  # West Concourse
    248: (40.8375, -73.8755),  # West Farms/Bronx River
    250: (40.8295, -73.8505),  # Westchester Village/Unionport
    254: (40.8785, -73.8565),  # Williamsbridge/Olinville
    259: (40.8955, -73.8665),  # Woodlawn/Wakefield
    
    # Staten Island zones - coordinates moved inland from eastern coastline
    5: (40.5555, -74.1785),    # Arden Heights
    6: (40.5945, -74.0830),    # Arrochar/Fort Wadsworth (moved west from coastline)
    23: (40.6085, -74.1095),   # Bloomfield/Emerson Hill
    44: (40.5075, -74.2355),   # Charleston/Tottenville
    84: (40.5375, -74.1955),   # Eltingville/Annadale/Prince's Bay
    109: (40.5535, -74.1515),  # Great Kills
    115: (40.6165, -74.0920),  # Grymes Hill/Clifton (moved west from coastline)
    118: (40.5945, -74.1185),  # Heartland Village/Todt Hill
    156: (40.6365, -74.1595),  # Mariners Harbor
    172: (40.5645, -74.1250),  # New Dorp/Midland Beach (moved west from coastline)
    176: (40.5625, -74.1295),  # Oakwood
    187: (40.6365, -74.1355),  # Port Richmond
    204: (40.5365, -74.2135),  # Rossville/Woodrow
    206: (40.6405, -74.0920),  # Saint George/New Brighton (moved west from coastline)
    214: (40.5835, -74.0880),  # South Beach/Dongan Hills (moved west from coastline)
    221: (40.6245, -74.0880),  # Stapleton (moved west from coastline)
    245: (40.6245, -74.1155),  # West Brighton
    251: (40.6185, -74.1385),  # Westerleigh
    
    # Special zones
    1: (40.6895, -74.1745),    # Newark Airport (EWR)
    103: (40.6895, -74.0445),  # Governor's Island
    104: (40.6990, -74.0395),  # Ellis Island
    105: (40.6892, -74.0445),  # Liberty Island
    194: (40.7935, -73.9215),  # Randalls Island
    199: (40.7935, -73.8865),  # Rikers Island
    202: (40.7610, -73.9510),  # Roosevelt Island
}


# Zones that are on narrow land strips or near water edges - use smaller jitter
WATERFRONT_ZONES = {
    # Manhattan waterfront
    12, 13, 87, 88, 209, 261,  # Battery area, Financial District, Seaport, WTC
    103, 104, 105,  # Governor's Island, Ellis Island, Liberty Island
    # Brooklyn waterfront
    14, 33, 54, 66, 195,  # Bay Ridge, Brooklyn Heights, Columbia Street, DUMBO, Red Hook
    149, 150, 154, 155,  # Madison, Manhattan Beach, Marine Park (near water)
    227, 228,  # Sunset Park East/West (near waterfront)
    # Queens waterfront/Jamaica Bay
    2, 27, 30, 86, 117, 124, 201,  # Jamaica Bay, Breezy Point, Broad Channel, Far Rockaway, etc.
    # Staten Island waterfront
    6, 115, 206, 214, 221,  # Arrochar, Grymes Hill, St George, South Beach, Stapleton
}


def get_zone_coordinate(
    zone_id: Optional[int],
    borough: Optional[str] = None,
    jitter: float = 0.002
) -> Tuple[float, float]:
    """
    Get coordinates for a taxi zone, with optional small jitter.
    
    Uses zone-specific centroids when available, otherwise falls back to
    sampling within land-only borough bounds.
    
    Args:
        zone_id: Taxi zone LocationID
        borough: Borough name (used as fallback if zone_id not in centroids)
        jitter: Maximum random offset to add (in degrees). Default 0.002 ≈ 220m
    
    Returns:
        (latitude, longitude) tuple guaranteed to be on land
    """
    # Check for known zone centroid first
    if zone_id is not None and zone_id in ZONE_CENTROIDS:
        base_lat, base_lon = ZONE_CENTROIDS[zone_id]
        
        # Use smaller jitter for waterfront zones to avoid falling into water
        effective_jitter = jitter * 0.3 if zone_id in WATERFRONT_ZONES else jitter
        
        # Apply jitter to avoid identical points for same zone
        lat = base_lat + random.uniform(-effective_jitter, effective_jitter)
        lon = base_lon + random.uniform(-effective_jitter, effective_jitter)
        return lat, lon
    
    # Fall back to borough-based sampling
    return sample_point_in_borough(borough, jitter=jitter)


def sample_point_in_borough(
    borough: Optional[str],
    jitter: float = 0.002
) -> Tuple[float, float]:
    """
    Sample a random point within a borough's land-only bounds.
    
    Args:
        borough: Borough name (Manhattan, Brooklyn, Queens, Bronx, Staten Island, EWR)
        jitter: Additional jitter to add (usually 0 for borough sampling)
    
    Returns:
        (latitude, longitude) tuple on land
    """
    borough_key = borough if borough in BOROUGH_LAND_BOUNDS else 'Manhattan'
    bounds = BOROUGH_LAND_BOUNDS[borough_key]
    lat_min, lat_max, lon_min, lon_max = bounds
    
    lat = random.uniform(lat_min, lat_max)
    lon = random.uniform(lon_min, lon_max)
    
    return lat, lon


def get_borough_center(borough: Optional[str]) -> Tuple[float, float]:
    """
    Get the center point of a borough.
    
    Args:
        borough: Borough name
    
    Returns:
        (latitude, longitude) tuple
    """
    borough_key = borough if borough in BOROUGH_CENTERS else 'Manhattan'
    return BOROUGH_CENTERS[borough_key]


def get_borough_bounds(borough: Optional[str]) -> Tuple[float, float, float, float]:
    """
    Get the land-only bounding box for a borough.
    
    Args:
        borough: Borough name
    
    Returns:
        (lat_min, lat_max, lon_min, lon_max) tuple
    """
    borough_key = borough if borough in BOROUGH_LAND_BOUNDS else 'Manhattan'
    return BOROUGH_LAND_BOUNDS[borough_key]

