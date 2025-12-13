import time
import json
import requests

from sqlmodel import Session, select
from agentbeats.model import engine, Agent, AgentHostedStatus
from agentbeats.gcp import upload_docker_to_gcp, launch_in_cloud_run, GCPSettings


def runner_loop():
    while True:
        time.sleep(1)
        with Session(engine) as session:
            # check the database for pending agents to launch
            statement = select(Agent).where(
                Agent.deploy_type == "hosted",
                Agent.hosted_status == "pending",
            )
            results = session.exec(statement)
            pending_agents = results.all()
            for agent in pending_agents:
                print(f"Found pending agent to launch: {agent.id}")
                try:
                    # upload docker image to GCP
                    gcp_image_url = upload_docker_to_gcp(agent)
                    print(f"Uploaded Docker image to GCP: {gcp_image_url}")
                    # launch in Cloud Run
                    inj_env = {}
                    if agent.secret:
                        inj_env = json.loads(agent.secret)
                    if agent.inject_litellm_proxy_api:
                        inj_env["LITELLM_PROXY_API_KEY"] = (
                            "sk-1drUa7BXyAibGKVo6PJYxQ"  # FIXME: use real key management
                        )
                        inj_env["LITELLM_PROXY_API_BASE"] = (
                            "https://dev1.agentbeats.org:12333"
                        )
                    response = launch_in_cloud_run(
                        agent,
                        gcp_image_url,
                        additional_env=inj_env,
                    )
                    print(f"Launched Agent {agent.id} in Cloud Run: {response}")
                    # update agent status in database
                    agent.hosted_status = AgentHostedStatus.STARTING
                    agent.gcp_docker_image_url = gcp_image_url
                    agent.gcp_cloudrun_service_name = "agent-" + str(agent.id)
                    gcp_settings = GCPSettings()
                    agent.ctrl_url = (
                        f"https://agent-{agent.id}-{gcp_settings.gcp_endpoint_suffix}"
                    )
                    session.add(agent)
                except Exception as e:
                    print(f"Error launching Agent {agent.id}: {e}")
                    agent.hosted_status = AgentHostedStatus.ERROR
                    agent.hosted_error_msg = str(e)
                    session.add(agent)
                session.commit()
                session.refresh(agent)
            # check the database for started agents to check ready
            statement = select(Agent).where(
                Agent.deploy_type == "hosted",
                Agent.hosted_status == AgentHostedStatus.STARTING,
            )
            results = session.exec(statement)
            starting_agents = results.all()
            for agent in starting_agents:
                print(f"Checking status of starting agent: {agent.id}")
                status_url = f"{agent.ctrl_url}/status"
                try:
                    resp = requests.get(status_url, timeout=5)
                    if resp.status_code == 200:
                        status_data = resp.json()
                        if status_data.get("running_agents") >= 1:
                            print(f"Agent {agent.id} is ready")
                            agent.hosted_status = AgentHostedStatus.RUNNING
                            session.add(agent)
                            session.commit()
                            session.refresh(agent)
                except Exception as _:
                    pass  # Not ready yet
