from datetime import UTC, datetime
from uuid import UUID

import httpx
from pydantic import SecretStr

from intelligence.agents.handover import HandoverAgent
from intelligence.config import CareLensSettings, WorkerIdentitySettings
from intelligence.connectors.authority import (
    HttpCareLensAuthorityReader,
    KeycloakCredentialProvider,
    require_secure_endpoint,
)
from intelligence.connectors.carelens import CareLensClient
from intelligence.gateway.handover import HandoverGateway
from intelligence.handover.authorization import CareLensExecutionAuthorizer, ExecutionAuthorizer
from intelligence.handover.contracts import GenerationMetadata
from intelligence.providers.fake_handover import FakeHandoverProvider
from intelligence.workflow.resident_handover import (
    run_resident_handover_workflow,
)


async def run_handover_task(*, tenant_id: UUID, job_id: UUID):
    identity = WorkerIdentitySettings()
    carelens = CareLensSettings()
    require_secure_endpoint(carelens.base_url)
    async with (
        httpx.AsyncClient(timeout=10, follow_redirects=False) as token_client,
        httpx.AsyncClient(
            base_url=carelens.base_url,
            timeout=carelens.timeout_seconds,
            follow_redirects=False,
        ) as authority_client,
    ):
        credentials = await KeycloakCredentialProvider(
            client=token_client,
            token_url=identity.token_url,
            client_id=identity.client_id,
            client_secret=identity.client_secret,
            expected_service_identity=identity.service_identity,
            minimum_lifetime_seconds=identity.minimum_token_lifetime_seconds,
        ).obtain()
        reader = HttpCareLensAuthorityReader(client=authority_client, access_token=credentials.access_token)
        authorizer = CareLensExecutionAuthorizer(
            reader, expected_service_identity=credentials.service_identity
        )
        return await execute_handover(
            tenant_id=tenant_id,
            job_id=job_id,
            authorizer=authorizer,
            access_token=credentials.access_token,
            generation_metadata=GenerationMetadata(
                agent_version=HandoverAgent.version,
                prompt_version="extractive-v1",
                gateway_version="handover-v1",
                provider="fake",
                model_version="deterministic-v1",
                generated_at=datetime.now(UTC),
            ),
        )


async def execute_handover(
    *,
    tenant_id: UUID,
    job_id: UUID,
    authorizer: ExecutionAuthorizer,
    access_token: SecretStr,
    generation_metadata: GenerationMetadata,
):
    settings = CareLensSettings()

    # Create the client inside this execution's event loop.
    # The context manager closes it on success or failure.
    async with httpx.AsyncClient(
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        follow_redirects=False,
    ) as http_client:
        client = CareLensClient(http_client, service_tenant_id=tenant_id)

        agent = HandoverAgent(
            gateway=HandoverGateway(
                provider=FakeHandoverProvider(),
                provider_timeout_seconds=30,
            ),
        )

        return await run_resident_handover_workflow(
            tenant_id=tenant_id,
            job_id=job_id,
            authorizer=authorizer,
            client=client,
            access_token=access_token,
            handover_agent=agent,
            generation_metadata=generation_metadata,
            reviewed_text_policy=None,
        )
