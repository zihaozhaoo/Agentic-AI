"""
Demo script to evaluate and compare baseline agents.
"""

import datetime
from white_agent import (
    DummyWhiteAgent,
    RegexBaselineAgent,
    RandomBaselineAgent,
    NaturalLanguageRequest,
    StructuredRequest,
    Location
)

def run_demo():
    # 1. Setup Agents
    agents = [
        DummyWhiteAgent(),
        RegexBaselineAgent(),
        RandomBaselineAgent()
    ]
    
    # 2. Create a sample request
    # "I need a ride from JFK Airport to Times Square"
    # Ground Truth: JFK (Zone ID 132) -> Times Sq (Zone ID 230)
    
    request_time = datetime.datetime.now()
    
    ground_truth = StructuredRequest(
        request_id="req_001",
        request_time=request_time,
        origin=Location(latitude=40.6413, longitude=-73.7781, zone_name="JFK Airport"),
        destination=Location(latitude=40.7580, longitude=-73.9855, zone_name="Times Sq/Theatre District"),
        passenger_count=1
    )
    
    nl_request = NaturalLanguageRequest(
        request_id="req_001",
        request_time=request_time,
        natural_language_text="I need a ride from JFK Airport to Times Sq/Theatre District please.",
        ground_truth=ground_truth
    )
    
    print(f"Input Text: '{nl_request.natural_language_text}'")
    print("-" * 60)
    
    # 3. Run each agent
    for agent in agents:
        print(f"Testing Agent: {agent.agent_name}")
        try:
            # Note: We are passing None for vehicle_database as parsing shouldn't strictly need it 
            # for these simple baselines, or we'd need to mock it.
            # RegexBaselineAgent loads zones from file, doesn't need DB for parsing.
            # Dummy needs ground truth.
            parsed = agent.parse_request(nl_request, vehicle_database=None)
            
            print(f"  Parsed Origin:      {parsed.origin.zone_name} (Lat/Lon: {parsed.origin.latitude:.2f}, {parsed.origin.longitude:.2f})")
            print(f"  Parsed Destination: {parsed.destination.zone_name} (Lat/Lon: {parsed.destination.latitude:.2f}, {parsed.destination.longitude:.2f})")
            
            # Simple accuracy check (Zone Name match)
            origin_match = parsed.origin.zone_name == ground_truth.origin.zone_name
            dest_match = parsed.destination.zone_name == ground_truth.destination.zone_name
            print(f"  Match Ground Truth? Origin: {origin_match}, Dest: {dest_match}")
            
        except Exception as e:
            print(f"  Error: {e}")
        print("-" * 60)

if __name__ == "__main__":
    run_demo()
