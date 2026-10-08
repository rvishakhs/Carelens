import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from intelligence.config import HandoverProviderSettings, OpenAIProviderSettings
from intelligence.gateway.preparation import prepare_handover
from intelligence.gateway.validation import validate_inbound_output
from intelligence.providers import runtime
from intelligence.providers.openai_handover import OpenAIHandoverProvider
from tests.support.fake_handover import FakeHandoverProvider
from tests.support.handover import make_input


def test_defaults_and_fake_rejected():
    assert OpenAIProviderSettings(api_key="test", _env_file=None).model == "gpt-6.1-sol"
    with pytest.raises(ValidationError):
        HandoverProviderSettings(provider="fake", _env_file=None)


def test_real_sdk_request_and_response_with_mock_transport():
    async def run():
        payload = prepare_handover(input=make_input()).payload
        expected = await FakeHandoverProvider().generate(payload)

        def handler(request):
            body = json.loads(request.content)
            assert body["store"] is False
            assert body["model"] == "test-model"
            assert body["max_output_tokens"] == 4096
            assert json.loads(body["input"]) == {"resident_alias": payload.resident_alias, "approved_claims": expected.model_dump(mode="json")["claims"]}
            assert body["text"]["format"]["strict"] is True
            return httpx.Response(
                200,
                json={
                    "id": "resp_test",
                    "object": "response",
                    "created_at": 1,
                    "model": "test-model",
                    "status": "completed",
                    "error": None,
                    "incomplete_details": None,
                    "output": [
                        {
                            "id": "msg_test",
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [
                                {"type": "output_text", "text": expected.model_dump_json(), "annotations": []}
                            ],
                        }
                    ],
                },
            )

        async with AsyncOpenAI(
            api_key="test",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ) as client:
            output = await OpenAIHandoverProvider(client=client, model="test-model").generate(payload)
            validate_inbound_output(output=output, payload=payload)

    asyncio.run(run())


@pytest.mark.parametrize("status,parsed", [("incomplete", None), ("completed", None)])
def test_no_usable_output_fails(status, parsed):
    async def run():
        client = SimpleNamespace(
            responses=SimpleNamespace(
                parse=AsyncMock(return_value=SimpleNamespace(status=status, output_parsed=parsed))
            )
        )
        with pytest.raises(RuntimeError, match="no structured"):
            await OpenAIHandoverProvider(client=client, model="test").generate(
                prepare_handover(input=make_input()).payload
            )

    asyncio.run(run())


def test_runtime_closes_client_on_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("INTELLIGENCE_HANDOVER_PROVIDER", "openai")
    client = AsyncMock()
    client.__aenter__.return_value = client
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return client

    monkeypatch.setattr(runtime, "AsyncOpenAI", factory)

    async def run():
        with pytest.raises(RuntimeError):
            async with runtime.open_provider_runtime() as selected:
                assert selected.provider == "openai"
                assert selected.model == "test-model"
                raise RuntimeError("workflow failure")

    asyncio.run(run())
    client.__aexit__.assert_awaited_once()
    assert calls[0]["max_retries"] == 0
    assert calls[0]["base_url"] == "https://api.openai.com/v1"
