from enum import Enum
from typing import Annotated
from datetime import datetime
from fastapi import Depends
from sqlmodel import SQLModel, Session, Field, create_engine
from sqlalchemy import Column, DateTime, func


class AgentDeployType(str, Enum):
    HOSTED = "hosted"
    REMOTE = "remote"
    PROXIED = "proxied"


class AgentHostedStatus(str, Enum):
    PENDING = "pending"  # or not hosted
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class Agent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), index=True
        ),
    )
    # agent types
    is_green: bool = Field(index=True)
    deploy_type: AgentDeployType = Field(index=True)
    ctrl_url: str | None
    agent_url: str | None  # mainly used for proxied agents
    # agent config
    secret: str
    inject_litellm_proxy_api: bool
    # -- three ways to instantiate hosted agents: git, docker, description_prompt
    git_url: str | None
    git_branch: str | None
    docker_image_url: str | None
    description_prompt: str | None
    # status
    hosted_status: AgentHostedStatus = Field(
        default=AgentHostedStatus.PENDING, index=True
    )
    hosted_error_msg: str | None
    gcp_docker_image_url: str | None
    gcp_cloudrun_service_name: str | None


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"


connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
