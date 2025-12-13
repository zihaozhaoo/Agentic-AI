from typing import Annotated
from contextlib import asynccontextmanager
from importlib.resources import files
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select


from agentbeats.model import (
    create_db_and_tables,
    SessionDep,
    Agent,
    AgentDeployType,
    AgentHostedStatus,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/agents/")
def create_agent(agent: Agent, session: SessionDep) -> Agent:
    if agent.id is not None:
        raise HTTPException(status_code=400, detail="ID should not be provided")
    if agent.created_at is not None:
        raise HTTPException(status_code=400, detail="created_at should not be provided")
    if agent.hosted_status != AgentHostedStatus.PENDING:
        raise HTTPException(
            status_code=400, detail="hosted_status should not be provided"
        )
    if agent.deploy_type == AgentDeployType.HOSTED:
        git_fields_provided = (agent.git_url is not None) and (
            agent.git_branch is not None
        )
        docker_field_provided = agent.docker_image_url is not None
        if not (git_fields_provided or docker_field_provided):
            raise HTTPException(
                status_code=400,
                detail="For hosted agents, either git_url and git_branch or docker_image_url must be provided",
            )
    else:
        if agent.git_url is not None or agent.git_branch is not None:
            raise HTTPException(
                status_code=400,
                detail="git_url and git_branch should be null for non-hosted agents",
            )
        if agent.docker_image_url is not None:
            raise HTTPException(
                status_code=400,
                detail="docker_image_url should be null for non-hosted agents",
            )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@app.get("/agents/")
def read_agents(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[Agent]:
    agents = session.exec(select(Agent).offset(offset).limit(limit)).all()
    return list(agents)


@app.get("/agents/{agent_id}")
def read_agent(agent_id: int, session: SessionDep) -> Agent:
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, session: SessionDep) -> dict:
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    session.delete(agent)
    session.commit()
    return {"message": "Agent deleted"}


@app.get("/test/add_test_tau_agents")
def add_test_tau_agents(session: SessionDep) -> dict:
    """Add test Tau agents to the database for testing purposes"""
    import datetime

    tau_green = Agent(
        name="Tau Green",
        created_at=datetime.datetime.utcnow(),
        is_green=True,
        deploy_type=AgentDeployType.HOSTED,
        ctrl_url="",
        agent_url="",
        secret='{"ROLE": "green"}',
        inject_litellm_proxy_api=True,
        git_url="",
        git_branch="",
        docker_image_url="us-west1-docker.pkg.dev/agentbeats/gcr-test/taubench-example:latest",
        description_prompt="",
        hosted_status=AgentHostedStatus.PENDING,
        hosted_error_msg=None,
        gcp_docker_image_url=None,
        gcp_cloudrun_service_name=None,
    )
    tau_white = Agent(
        name="Tau White",
        created_at=datetime.datetime.utcnow(),
        is_green=False,
        deploy_type=AgentDeployType.HOSTED,
        ctrl_url="",
        agent_url="",
        secret='{"ROLE": "white"}',
        inject_litellm_proxy_api=True,
        git_url="",
        git_branch="",
        docker_image_url="us-west1-docker.pkg.dev/agentbeats/gcr-test/taubench-example:latest",
        description_prompt="",
        hosted_status=AgentHostedStatus.PENDING,
        hosted_error_msg=None,
        gcp_docker_image_url=None,
        gcp_cloudrun_service_name=None,
    )
    session.add(tau_green)
    session.add(tau_white)
    session.commit()
    session.refresh(tau_green)
    session.refresh(tau_white)
    return {"message": "Test Tau agents added successfully"}


@app.get("/test_agent_crud", response_class=HTMLResponse)
async def test_agent_crud():
    """Serve the Agent CRUD frontend interface"""
    html_content = files("agentbeats.frontend").joinpath("agent_crud.html").read_text()
    return html_content


@app.get("/")
async def root():
    # redirect to test_agent_crud
    return RedirectResponse(url="/test_agent_crud")
