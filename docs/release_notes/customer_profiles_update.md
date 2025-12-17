# Changes: Customer Profile Integration for Personal Location Resolution

**Date**: 2025-12-14
**Feature**: Enable white agents to resolve personal location references (e.g., "my house", "work", "office")

## Overview

This update implements customer profile integration to allow white agents to accurately parse natural language requests containing personal location references. Previously, when a user said "pick me up at my house," the white agent had no way to know where the customer's house was located. Now, customer profile information is passed to the white agent and included in the LLM context.

## Problem Statement

**Before**: White agents could not resolve personal location references because:
- No customer information was passed to the white agent
- `NaturalLanguageRequest` only contained the natural language text
- Google Maps geocoding "my house, New York, NY" would fail or return meaningless results
- Parsing accuracy suffered on ~30% of requests that used personal references

**After**: White agents receive customer_id and can:
- Fetch customer profile from the customer database
- Access home, work, and frequent location information
- Provide this context to the LLM for accurate extraction
- Successfully parse personal location references

---

## Files Changed

### 1. `src/white_agent/data_structures.py`

**Purpose**: Add customer_id field to request data structure

**Changes**:
```python
@dataclass
class NaturalLanguageRequest:
    request_id: str
    request_time: datetime
    natural_language_text: str

    # NEW: Customer information for resolving personal location references
    customer_id: Optional[str] = None

    ground_truth: Optional[StructuredRequest] = None
```

**Impact**: Customer ID can now flow from green agent to white agent

---

### 2. `src/environment/green_agent_environment.py`

**Purpose**: Pass customer_id when creating NaturalLanguageRequest

**Changes** (line ~668):
```python
return NaturalLanguageRequest(
    request_id=str(request_data.get('trip_id', '')),
    request_time=request_data.get('request_time', datetime.now()),
    natural_language_text=nl_text,
    customer_id=request_data.get('customer_id'),  # ← NEW
    ground_truth=ground_truth
)
```

**Impact**: Green agent now forwards customer_id from request simulator to white agent

---

### 3. `src/white_agent/base_agent.py`

**Purpose**: Enable customer profile lookup and inject context into LLM

#### A. Constructor Updates

**WhiteAgentBase**:
```python
def __init__(self, agent_name: str, config: Optional[Dict[str, Any]] = None,
             customer_db: Optional[Any] = None):  # ← NEW parameter
    self.agent_name = agent_name
    self.config = config or {}
    self.customer_db = customer_db  # ← NEW
```

**DummyWhiteAgent**:
```python
def __init__(self, agent_name: str = "DummyAgent", config: Optional[Dict[str, Any]] = None,
             customer_db: Optional[Any] = None):  # ← NEW parameter
    super().__init__(agent_name, config, customer_db)  # ← Pass to parent
```

**NaturalLanguageAgent**:
```python
def __init__(self, agent_name: str = "NaturalLanguageAgent",
             config: Optional[Dict[str, Any]] = None,
             customer_db: Optional[Any] = None):  # ← NEW parameter
    super().__init__(agent_name, config, customer_db)  # ← Pass to parent
    # ... rest of initialization
```

#### B. New Method: Customer Context Retrieval

**Added** (lines 429-466):
```python
def _get_customer_context(self, customer_id: Optional[str]) -> str:
    """
    Get customer profile information for LLM context.

    Args:
        customer_id: Customer ID

    Returns:
        Formatted string with customer profile information for LLM prompt
    """
    if not customer_id or not self.customer_db:
        return ""

    profile = self.customer_db.get_profile(customer_id)
    if not profile:
        return ""

    # Format customer profile information
    context_parts = ["\n## Customer Profile Information"]
    context_parts.append(f"Customer ID: {profile.customer_id}")

    # Add home location
    if profile.home:
        context_parts.append(f"- Home: {profile.home.zone_name}, {profile.home.borough} (Zone ID: {profile.home.zone_id})")

    # Add work location
    if profile.work:
        context_parts.append(f"- Work/Office: {profile.work.zone_name}, {profile.work.borough} (Zone ID: {profile.work.zone_id})")

    # Add frequent locations
    if profile.frequent_locations:
        context_parts.append("- Frequent locations:")
        for loc in profile.frequent_locations:
            context_parts.append(f"  * {loc.label}: {loc.zone_name}, {loc.borough} (Zone ID: {loc.zone_id})")

    context_parts.append("\nWhen the user mentions personal locations like 'home', 'my house', 'work', 'office', etc., use the addresses from this profile.")

    return "\n".join(context_parts)
```

**Purpose**: Fetches customer profile and formats it into LLM-readable context

#### C. Enhanced Parsing with Customer Context

**Modified** `parse_request()` (lines 494-524):
```python
def parse_request(self, nl_request: NaturalLanguageRequest,
                  vehicle_database: 'VehicleDatabase') -> StructuredRequest:
    nl_text = nl_request.natural_language_text
    current_time_str = nl_request.request_time.isoformat()

    # NEW: Get customer context if available
    customer_context = self._get_customer_context(nl_request.customer_id)

    # NEW: Include customer context in system prompt
    system_prompt = (
        f"You are a ride-hailing dispatcher in NYC. Current time: {current_time_str}. "
        "Extract the pickup and dropoff addresses or POI names for locations in New York City. "
        "All locations should be assumed to be in NYC unless explicitly stated otherwise. "
        "Resolve relative times (e.g. 'in 10 mins') to absolute ISO timestamps."
        f"{customer_context}"  # ← Customer profile injected here
    )

    # Continue with OpenAI parsing...
```

**Impact**: LLM now receives customer's personal location information in the system prompt

---

## Example LLM Context

When a customer (ID: CUST_000123) requests "Pick me up at my house", the LLM receives:

```
You are a ride-hailing dispatcher in NYC. Current time: 2025-01-15T14:30:00.
Extract the pickup and dropoff addresses or POI names for locations in New York City.
All locations should be assumed to be in NYC unless explicitly stated otherwise.
Resolve relative times (e.g. 'in 10 mins') to absolute ISO timestamps.

## Customer Profile Information
Customer ID: CUST_000123
- Home: Upper East Side, Manhattan (Zone ID: 234)
- Work/Office: Midtown, Manhattan (Zone ID: 186)
- Frequent locations:
  * gym: Chelsea, Manhattan (Zone ID: 45)

When the user mentions personal locations like 'home', 'my house', 'work', 'office', etc., use the addresses from this profile.
```

The LLM can now extract "Upper East Side" as the pickup location instead of failing on "my house".

---

## Usage

### Initializing White Agent with Customer Database

```python
from request_simulation import CustomerProfileDatabase
from white_agent import NaturalLanguageAgent

# 1. Initialize customer database (same instance used by request simulator)
customer_db = CustomerProfileDatabase("taxi_zone_lookup.csv")
customer_db.generate_profiles(200)

# 2. Initialize white agent WITH customer database
white_agent = NaturalLanguageAgent(
    agent_name="SmartAgent",
    customer_db=customer_db  # ← Pass customer database
)

# 3. Use in evaluation
env = GreenAgentEnvironment(request_simulator=request_simulator)
results = env.run_evaluation(white_agent=white_agent, requests=requests)
```

### How It Works End-to-End

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Request Simulator                                            │
│    - Assigns customer_id to ~30% of trips                       │
│    - Generates NL: "Pick me up at my house"                     │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Green Agent Environment                                      │
│    - Creates NaturalLanguageRequest with customer_id            │
│    - Passes to white agent                                      │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. White Agent (NaturalLanguageAgent)                           │
│    - Receives customer_id in nl_request                         │
│    - Calls _get_customer_context(customer_id)                   │
│    - Fetches profile from customer_db                           │
│    - Formats home/work/frequent locations                       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. OpenAI LLM                                                   │
│    - Receives system prompt WITH customer profile info          │
│    - Sees "my house" in user message                            │
│    - Maps to "Upper East Side" from profile                     │
│    - Extracts: poi_name="Upper East Side"                       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Google Maps Geocoding                                        │
│    - Geocodes "Upper East Side, New York, NY"                   │
│    - Returns coordinates: (40.7736, -73.9566)                   │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. Result                                                       │
│    ✅ Accurate parsing of personal location reference           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Backward Compatibility

All changes are **fully backward compatible**:

- ✅ `customer_id` is optional in `NaturalLanguageRequest`
- ✅ `customer_db` is optional in white agent constructors
- ✅ If no customer_db provided, agent works as before
- ✅ If customer_id is None, no context is added to prompt
- ✅ Existing agents without customer database support continue to work

---

## Testing Personal Location Resolution

```python
# Test case: Customer with known profile
customer_db = CustomerProfileDatabase("taxi_zone_lookup.csv")
profile = customer_db.generate_profile(
    customer_id="TEST_001",
    home_zone=234,  # Upper East Side
    work_zone=186   # Midtown
)
customer_db.profiles[profile.customer_id] = profile

# Create request with personal reference
nl_request = NaturalLanguageRequest(
    request_id="test_001",
    request_time=datetime.now(),
    natural_language_text="Pick me up at home and take me to work",
    customer_id="TEST_001"
)

# Parse with agent
white_agent = NaturalLanguageAgent(customer_db=customer_db)
structured = white_agent.parse_request(nl_request, vehicle_db)

# Verify: Should extract Upper East Side → Midtown trip
assert structured.origin.zone_id == 234
assert structured.destination.zone_id == 186
```

---

## Evaluation Metrics Impact

With this change, the evaluation logging now properly tracks:

- `origin_distance_error_miles`: Distance between parsed and ground truth origin
- `destination_distance_error_miles`: Distance between parsed and ground truth destination
- `parse_ok`: Whether both errors are < 100 miles (now includes personal references)

**Expected improvements**:
- ↑ Origin zone accuracy for requests with personal pickup locations
- ↑ Destination zone accuracy for requests with personal dropoff locations
- ↑ Overall parsing score on the ~30% of requests using personal references
- ↓ Mean origin/destination distance errors

---

## Related Changes

See also:
- Evaluation metrics update in `src/evaluation/evaluator.py` (lines 334-335)
- Distance error logging in `src/environment/green_agent_environment.py` (lines 343-374)
- Customer profile system in `src/request_simulation/customer_profiles.py`

---

## Future Enhancements

Potential improvements for future versions:

1. **Fuzzy Matching**: Handle variations like "my place", "my apartment", "home sweet home"
2. **Context Memory**: Remember previous trips to infer likely locations
3. **Multi-User Households**: Handle "my house" vs "my parents' house"
4. **Real-Time Updates**: Allow customers to update their profile locations
5. **Privacy Controls**: Let customers opt-out of profile sharing with agents

---

## Migration Guide

### For Existing Code Using White Agents

**Before**:
```python
agent = NaturalLanguageAgent(agent_name="MyAgent")
```

**After** (with customer profile support):
```python
# Initialize customer database first
from request_simulation import CustomerProfileDatabase
customer_db = CustomerProfileDatabase("taxi_zone_lookup.csv")
customer_db.generate_profiles(200)

# Pass to agent
agent = NaturalLanguageAgent(
    agent_name="MyAgent",
    customer_db=customer_db
)
```

**Note**: If you don't pass `customer_db`, the agent still works but won't resolve personal references.

---

## Summary

This update makes the white agent evaluation system more realistic by:
- ✅ Mirroring real ride-hailing apps that know user profiles
- ✅ Enabling fair evaluation on requests with personal references
- ✅ Testing agents' ability to integrate multiple data sources
- ✅ Maintaining backward compatibility with existing code
- ✅ Providing clear, interpretable customer context to LLMs

The implementation is clean, well-documented, and ready for production use.
