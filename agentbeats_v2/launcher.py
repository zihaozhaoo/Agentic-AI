"""Launcher - starts green/white agents and triggers evaluation via A2A."""

import multiprocessing
import asyncio
import textwrap
import json
from pathlib import Path

from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent
from src.my_util import my_a2a


async def launch_workflow():
    green_host, green_port = "localhost", 9101
    white_host, white_port = "localhost", 9102

    green_url = f"http://{green_host}:{green_port}"
    white_url = f"http://{white_host}:{white_port}"

    # Start green agent (avoid double-start if already running)
    p_green = None
    if await my_a2a.wait_agent_ready(green_url, timeout=2):
        print(f"Green agent already running at {green_url}, not starting a new one.")
    else:
        print("Launching green agent...")
        p_green = multiprocessing.Process(
            target=start_green_agent, args=("ride_green_agent", green_host, green_port)
        )
        p_green.start()
        assert await my_a2a.wait_agent_ready(green_url), "Green agent not ready in time"
        print("Green agent ready.")

    # Start white agent (optional demo target)
    p_white = None
    if await my_a2a.wait_agent_ready(white_url, timeout=2):
        print(f"White agent already running at {white_url}, not starting a new one.")
    else:
        print("Launching white agent...")
        p_white = multiprocessing.Process(
            target=start_white_agent, args=("sample_white_agent", white_host, white_port)
        )
        p_white.start()
        assert await my_a2a.wait_agent_ready(white_url), "White agent not ready in time"
        print("White agent ready.")

    # Build task message to green agent
    task_cfg = {
        "agent_name": "nearest",  # options: nearest, dummy, regex, random
        "num_requests": 20,
        "num_vehicles": 50,
    }
    task_text = textwrap.dedent(
        f"""
        Run the ride-hailing baseline evaluation with the following config:
        <agent_name>{task_cfg['agent_name']}</agent_name>
        <num_requests>{task_cfg['num_requests']}</num_requests>
        <num_vehicles>{task_cfg['num_vehicles']}</num_vehicles>
        <white_agent_url>{white_url}</white_agent_url>
        """
    ).strip()

    print("Sending task to green agent...")
    response = await my_a2a.send_message(green_url, task_text)
    print("Response from green agent:")
    print(response)

    print("Shutting down agents...")
    if p_green is not None:
        p_green.terminate()
        p_green.join()
    if p_white is not None:
        p_white.terminate()
        p_white.join()
    print("Done.")
