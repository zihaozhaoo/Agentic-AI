"""CLI entry point for AgentBeats v2 wrapper around our ride-hailing baselines."""

import typer
import asyncio

from launcher import launch_workflow
from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent

app = typer.Typer(help="AgentBeats v2 (A2A) harness for ride-hailing baselines")


@app.command()
def green():
    """Start the green agent (evaluation orchestrator)."""
    start_green_agent()


@app.command()
def white():
    """Start the sample white agent (LLM echo)."""
    start_white_agent()


@app.command()
def launch():
    """Launch green/white agents and run a baseline evaluation via A2A."""
    asyncio.run(launch_workflow())


if __name__ == "__main__":
    app()
