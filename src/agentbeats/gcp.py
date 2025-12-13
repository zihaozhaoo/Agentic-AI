from pydantic_settings import BaseSettings, SettingsConfigDict
from google.cloud import run_v2
from google.cloud.run_v2.types import IngressTraffic
from agentbeats.model import Agent


class GCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    gcp_project_id: str | None = None
    gcp_region: str | None = None
    gcp_repo_name: str = "agentbeats-agent-repo"
    gcp_endpoint_suffix: str | None = None


def upload_docker_to_gcp(a: Agent):
    import docker

    client = docker.from_env()

    # Required: need to configure the gcp credentials, the container repo, and docker auth first
    assert a.docker_image_url is not None
    # Plan:
    # 1. Pull the docker image from the specified URL
    client.images.pull(a.docker_image_url)
    # 2. Tag the image for GCP Container Registry
    s = GCPSettings()
    gcp_image_url = f"{s.gcp_region}-docker.pkg.dev/{s.gcp_project_id}/{s.gcp_repo_name}/agent-{a.id}:latest"
    image = client.images.get(a.docker_image_url)
    image.tag(gcp_image_url)
    # 3. Push the image to GCP Container Registry
    client.images.push(gcp_image_url)
    # 4. Return the GCP image URL
    return gcp_image_url


def launch_in_cloud_run(a: Agent, gcp_image_url: str, additional_env: dict = {}):
    client = run_v2.ServicesClient()
    s = GCPSettings()
    request = run_v2.CreateServiceRequest(
        parent=f"projects/{s.gcp_project_id}/locations/{s.gcp_region}",
        service_id=f"agent-{a.id}",
        service=run_v2.Service(
            description=f"AgentBeats Agent {a.id} Service",
            template=run_v2.RevisionTemplate(
                containers=[
                    run_v2.Container(
                        image=gcp_image_url,
                        ports=[run_v2.ContainerPort(container_port=8080)],
                        resources=run_v2.ResourceRequirements(
                            limits={"cpu": "4", "memory": "8Gi"},
                        ),
                        env=[
                            run_v2.EnvVar(name="HTTPS_ENABLED", value="true"),
                            run_v2.EnvVar(
                                name="CLOUDRUN_HOST",
                                value=f"agent-{a.id}-{s.gcp_endpoint_suffix}",
                            ),
                            *[
                                run_v2.EnvVar(name=k, value=v)
                                for k, v in additional_env.items()
                            ],
                        ],
                    )
                ],
                # manual scaling with 1 instance
                scaling=run_v2.RevisionScaling(
                    min_instance_count=1,
                    max_instance_count=1,
                ),
            ),
            ingress=IngressTraffic.INGRESS_TRAFFIC_ALL,
            invoker_iam_disabled=True,
        ),
    )
    response = client.create_service(request=request)
    return response


if __name__ == "__main__":
    # Test upload function
    import datetime
    import random
    from agentbeats.model import AgentDeployType

    a = Agent(
        id=random.randint(1000, 9999),
        name="test-agent",
        created_at=datetime.datetime.now(),
        is_green=True,
        deploy_type=AgentDeployType.HOSTED,
        ctrl_url="",
        agent_url="",
        secret="",
        inject_litellm_proxy_api=True,
        git_url="",
        git_branch="",
        docker_image_url="us-west1-docker.pkg.dev/agentbeats/gcr-test/taubench-example",
        description_prompt="",
        hosted_error_msg=None,
        gcp_docker_image_url=None,
        gcp_cloudrun_service_name=None,
    )
    gcp_url = upload_docker_to_gcp(a)
    print(f"Uploaded to GCP Container Registry: {gcp_url}")

    r = launch_in_cloud_run(a, gcp_url, additional_env={"ROLE": "white"})
    print(f"Launching Agent {a.id} in Cloud Run: {r}")
