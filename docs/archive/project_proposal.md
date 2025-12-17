
# [CS294/194-196 Agentic AI](https://rdi.berkeley.edu/agentic-ai/f25)

# Team Name

# Title

Evaluating dynamic ride-hailing dispatch with natural language requests

# Abstract

We propose an evaluation framework for the urban real-time routing allocation problem. A green agent emits realistic, online, language-based ride requests and maintains a dynamic driver state; the white agent must parse these demands and assign incoming requests to drivers. Performance is evaluated on both demand understanding and final routing cost, enabling robust, fair, and adaptive comparison of allocation methods for efficiency, responsiveness, and sustainability in complex urban mobility scenarios.

# Task Description

The green agent evaluates urban real-time ride allocation and routing. It simulates a live mobility service where passenger ride requests appear one by one in natural language, including origin, destination, time, and other constraints. The system keeps track of a changing driver fleet locations, availability, and completed trips, and updates this state as rides are assigned.  
Participants (white agents) must interpret each request, match it with an appropriate driver, and produce an updated allocation and route plan in real time. The environment introduces realistic fluctuations such as rush-hour surges and uneven regional demand, and performance is measured on both how accurately requests are understood and how efficient the resulting fleet operations are (minimizing unmet demand and unnecessary empty driving).

# Related Work

[https://arxiv.org/abs/2505.17734](https://arxiv.org/abs/2505.17734)**:**  urban routing benchmark for RL on real traffic networks . Focuses on route choice and congestion metrics for autonomous fleets. 

[https://arxiv.org/pdf/2305.18859](https://arxiv.org/pdf/2305.18859): DARP (Dial-a-Ride Problem) request dataset in NYC solved with insertion heuristic. 

Novelty of our design: LLM demand understanding, online response

# Evaluation Design (Baihe

**Objective.**  
 The goal of the evaluation design is to construct a green agent that functions as a hosting and coordinating evaluator for white agents developed to address urban real-time ride allocation problems. The green agent’s primary objective is to provide a robust, reproducible, and adaptive evaluation environment capable of simulating realistic urban dynamics. This includes generating dynamic user demand patterns, maintaining evolving driver datasets, and quantitatively assessing the performance of white agents across diverse operational scenarios. Through this design, the evaluation framework aims to benchmark white agents not only for computational efficiency and allocation accuracy but also for adaptability under varying temporal and spatial demand distributions. We use a state-of-the-art system-level objective that balances unmet demand penalties with idle (deadhead) cruising effort, which reflects long-standing assignment goals and captures modern platform-level efficiency under spatiotemporal imbalance. 

**Environment and Judging Pipeline.**  
 The evaluation pipeline is structured into four main phases. (1) **Synthetic Demand Generation:** The green agent dynamically generates user queries representing ride requests with randomized yet statistically grounded origin–destination pairs and timestamps, emulating real-world fluctuations in urban mobility demand (e.g., peak-hour surges or regional concentration effects). (2) **Agent Querying:** These demands are sequentially submitted to the white agent, which must produce a driver allocation and routing plan that satisfies the current and anticipated demands. (3) **Dynamic Dataset Maintenance:** Throughout the simulation, the green agent maintains and updates the driver dataset—tracking availability, locations, and completed rides—to ensure temporal consistency and evolving state representations. (4) **Performance Evaluation:** After processing all ride requests, the green agent computes performance metrics using well-established cost functions combining demand-supply and idle cruising which penalizes (a) unsatisfied demand due to local shortages and (b) deadhead cruising used to rebalance supply.

**Evaluation Metric.**

The green agent evaluates each white agent based on a **net-revenue** metric that integrates both platform earnings and driver efficiency. The core objective is to maximize the total revenue generated from completed rides minus the operational cost incurred during idle or deadhead periods. The resulting net revenue captures the trade-off between maximizing service coverage (high total fare) and minimizing inefficient repositioning or waiting (idle cost). This formulation extends classical dispatch metrics—focused solely on travel distance or waiting time—by explicitly incorporating an economic efficiency perspective, consistent with recent literature in fleet optimization and ride-hailing platform management. Through this unified metric, the green agent produces interpretable and comparable evaluations of how well each white agent balances profitability and sustainability under dynamic urban conditions.

**Example Use Cases / Scenarios.**

The proposed evaluation framework can be applied to a range of realistic urban mobility scenarios, enabling comparative analysis of diverse white agent strategies under controlled yet dynamic conditions. For instance, in a peak-hour surge scenario, the green agent can generate temporally clustered ride demands concentrated in central business districts, testing a white agent’s ability to efficiently allocate limited drivers under time pressure. In contrast, an off-peak spatial imbalance scenario can simulate sparse but geographically dispersed requests, evaluating how well an agent repositions idle drivers to maintain service coverage while minimizing unnecessary travel. A ride-sharing coordination scenario can further extend the test environment by introducing multi-passenger ride matching, requiring the white agent to balance pickup detours with overall platform throughput. Additionally, a sustainability-focused scenario can incorporate fuel consumption or carbon emission estimates into the idle cost, assessing the environmental implications of different dispatch policies. Together, these use cases demonstrate how the green agent enables flexible, data-driven benchmarking of white agents across economic, operational, and environmental dimensions within urban mobility ecosystems.

**Platform.**  
 The green agent operates as the central orchestrator of the simulation environment, managing communication, state updates, and external data access. It initiates interaction by issuing structured demand messages to the white agent through a standardized interface (e.g., JSON-based API). The white agent responds with an allocation plan specifying driver–user pairings, predicted travel times, and any auxiliary information needed for downstream evaluation. During simulation, the green agent maintains global synchrony by continuously updating environment states—driver positions, ride progress, and system time—and logging all transactions for reproducibility and traceability. To ensure realistic spatial modeling, the green agent provides a connection to the **Google Maps API**, enabling the white agent to query estimated travel times or distances between locations dynamically. After all user demands have been processed, the green agent aggregates the logs and computes the defined cost metrics. This modular and API-driven environment ensures that any white agent, regardless of its internal policy or learning paradigm, can be evaluated consistently within a transparent and extensible benchmarking ecosystem.

# Data & Environment Design (Hengyu

## **Project Proposal \- Data & Environment Design**

### **1\. Dataset Design**

#### **1.1 Source Data**

We generate user request data based on **NYC TLC High-Volume For-Hire Vehicle (HVFHV) data ([https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) )**, selected for its comprehensive temporal and operational detail:

* **Coverage**: 20+ million trips/month from Uber, Lyft, Via, Juno (Feb 2019-present)  
* **Key fields**: request\_datetime, pickup/dropoff locations (263 taxi zones), trip\_miles, trip\_time, passenger\_count, shared ride flags, accessibility flags, fare details  
* **Geographic granularity**: Neighborhood-level zones with shapefiles for spatial analysis  
* **Format**: Apache Parquet files for efficient processing

#### **1.2 Data Preprocessing**

We first do quality filtering: remove invalid LocationIDs, impossible timestamps, negative values, and inconsistent distances. Then we enrich the data with more spatial information, such as including taxi zone metadata (borough, zone names), calculating inter-zone distances and travel time distributions and adding Points of Interest (POI) from OpenStreetMap/Google Places. After data preprocessing, we obtain a clear structured dataset of trip records.

**1.3 Benchmark Dataset size**:

* Development: 100K trips  
* Validation: 50K trips  
* Test: 100K trips

### **2\. Natural Language Generation**

We convert structured trip records into natural language requests that AI agents must parse.

#### **2.1 Hybrid Generation (50% Templates \+ 50% Neural)**

**Template Tiers** (50% of data):

1. **Basic**: "I need a taxi from Times Square to JFK Airport at 3:30 PM"  
2. **POI-based**: "Pick me up at Grand Central and take me to the Empire State Building"  
3. **Time-constrained**: "I need to arrive at LaGuardia by 5 PM for my flight"  
4. **Multi-stop**: "Pick me up at Penn Station, stop at Brooklyn, then to JFK"  
5. **Complex**: "Wheelchair-accessible vehicle from 57th St to JFK Terminal 4, 2 passengers, 3 bags, arrive by 5 PM"

**Neural Generation** (50% of data):

* Generate natural language requests that include more flexibility using LLMs API，such as ChatGPT/Claude, e.t.c.

### **3\. Vehicle Database Design**

#### **3.1 Database Schema**

**Vehicle State Table** :

* state\_id, vehicle\_id, availability\_status, current\_zone\_id, location  
* valid\_from/valid\_to (real-world time), transaction\_from/transaction\_to (audit trail)

#### **3.2 Fleet Initialization Strategy**

Since NYC TLC provides no vehicle location data, we distribute new vehicles proportional to demand patterns and initialize their locations randomly.

**Fleet Size**: \~77,000 HVFHV vehicles, 8,000 yellow taxis (based on NYC 2023 data)

**Spatial Indexing**: PostGIS with GIST indexes for fast nearest-vehicle queries (\<100ms)

### **4\. Benchmark Architecture**

#### **4.1 Three-Agent System**

1. **Green Agent (User Request Simulation)**: Samples trips, generates NL requests at request\_datetime  
2. **White Agent (Under Test)**: Parses NL → structured parameters via API  
3. **Backend Routing (Under Test)**: Assigns vehicles using routing algorithm  
4. **Green Agent (Evaluator)**: Computes all metrics, generates scores

#### **4.2 Execution Flow**

**Initialization** (6 AM): Initialize vehicle fleet with random locations

**Simulation** (6 AM \- 6 PM, 12 hours):

For each request chronologically:  
  1\. Generate NL request  
  2\. White Agent parses → structured data  
  3\. Validate parsing  
  4\. Backend assigns vehicle  
  5\. Update vehicle states  
  6\. Log for evaluation

**Evaluation**: Compute metrics, compare to baselines, generate reports

---

# Estimated Timeline and Concrete Step (Zihao

### **Phase 1: Green Agent Development**

**By 10/8 — Proposal (Current Submission)**

* Finalize scope, responsibilities, and evaluation goals

* Align modules (parser, routing, synthetic data, evaluator) with dataset assumptions

**10/8–10/20 — Demo Preparation and MVP Pipeline**  
 Goal: deliver a runnable demo and short report by 10/20

* Set up repository structure and simulation environment

* Implement request ingestion and driver state initialization

* Draft baseline parser and minimal white agent interface

* Build simple evaluation loop (e.g., batch of synthetic requests)

* Run small-scale test and produce demo recording

**10/20–11/3 — Full Implementation and Documentation**  
 Goal: final green agent submission by 11/3

* Integrate key modules:

  * synthetic demand generation

  * routing and evaluator (e.g., OR-Tools baseline)

  * parser integration

* Add metrics: unmet demand, parsing accuracy, dispatch success

* Enable logging and reproducibility settings

* Write documentation and record final demo

---

### **Phase 2 (If Selected as Top 3 Green Agent)**

Top 3 teams announced by 11/9

**11/10–11/17 — Competition Agent Proposal**

* Upgrade from baseline to competitive strategy

* Define optimization direction (e.g., fairness, speed, efficiency)

**11/17–12/12 — Final Competition Agent Implementation**

* Scale up simulation and integrate improvements

* Add stress testing (rush hour, uneven distribution, edge cases)

* Deliver final report and implementation by 12/12

# Division of Labor 

**Baihe**

* Natural language request parsing

* White agent interaction and structured output schema

* System testing and documentation support

**Hengyu**

* Dataset preprocessing (NYC TLC HVFHV)

* Routing logic and spatial–temporal feature integration

* Contribution to synthetic request generation and stress testing

**Wolin**

* System integration across components

* Debugging, experiment setup, and tooling support

* Assistance across routing, parsing, and evaluation modules

**Zihao**

* Simulation flow setup (request streaming, driver state, logging)

* Evaluation metrics and pipeline coordination

* Participation in synthetic data generation and documentation

---

### **Collaboration Across Phases**

**Phase 1 (Now–11/3): Green Agent Development**  
 All members will jointly contribute to:

* Proposal drafting

* MVP implementation and demo (due 10/20)

* Final implementation, documentation, and recording (due 11/3)

Shared tasks include:

* Synthetic demand generation

* Parsing and routing integration

* Evaluation loop design

* Testing and refinements

**Phase 2 (If selected as Top 3 on 11/9)**  
 All members will collaborate on:

* Competition agent proposal (11/10–11/17)

* Final implementation and report (11/17–12/12)

Shared responsibilities include:

* Evaluation improvements

* Routing and demand-side optimization

* Interaction robustness

* Stress testing and reporting

# Benchmarks

N.A

