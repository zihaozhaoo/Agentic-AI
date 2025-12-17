# Agentic AI: Green Agent Framework

A comprehensive framework for evaluating AI agents on urban ride-hailing dispatch tasks.

## 🚀 Overview

This project provides a complete environment to simulate, develop, and evaluate "White Agents" (dispatch algorithms) that manage ride-hailing fleets. It includes:

- **Request Simulation**: Generates realistic natural language ride requests from NYC taxi data.
- **Vehicle System**: Simulates fleet movement, availability, and state.
- **Evaluation Engine**: Scores agents on parsing accuracy, revenue generation, and routing efficiency.
- **Green Agent Environment**: Orchestrates the interaction between the fleet, the requests, and your agent.

## 📚 Documentation

- **[Getting Started](docs/getting_started.md)**: Zero-to-hero guide to running your first evaluation.
- **[Framework Overview](docs/framework_overview.md)**: Deep dive into the system architecture and components.
- **[Component Guide](docs/guides/component_guide.md)**: Detailed API reference.
- **[Request Simulation Guide](docs/guides/request_simulation_quickstart.md)**: How to generate and customize synthetic requests.
- **[Deployment & Testing](docs/guides/deployment_testing.md)**: Guide for deploying and testing the system.

## 🛠 Project Structure

```text
├── src/
│   ├── request_simulation/  # Natural language request generation
│   ├── vehicle_system/      # Fleet management and simulation
│   ├── white_agent/         # Dispatch agent interfaces
│   ├── evaluation/          # Scoring metrics
│   └── environment/         # Main simulation orchestrator
├── examples/                # Usage examples and demos
├── docs/                    # Documentation and guides
└── tests/                   # Unit and integration tests
```

## ⚡️ Quick Start

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the demo evaluation**:

   ```bash
   python examples/demo_evaluation.py
   ```

3. **Check the results** in the `results/` directory.

## 📅 Roadmap

Check the **[Implementation Roadmap](docs/implementation_roadmap.md)** for upcoming features and tasks, including:

- NLP-based request parsing.
- Intelligent routing algorithms.
- Google Maps / OSRM integration.

## 📝 Release Notes

- **[Customer Profiles Update](docs/release_notes/customer_profiles_update.md)** (2025-12-14)
