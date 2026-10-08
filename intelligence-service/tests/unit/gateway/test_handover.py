import asyncio

import pytest

from intelligence.gateway.handover import (
    HandoverGateway,
    HandoverProviderError,
    HandoverProviderTimeout,
)
from intelligence.gateway.privacy import PrivacyRejected
from intelligence.gateway.validation import InboundValidationError
from intelligence.handover.input_validation import (
    InternalInputValidationError,
)
from tests.support.fake_handover import FakeHandoverProvider
from tests.support.handover import make_input, with_notes


class SpyProvider:
    def __init__(self):
        self.calls = 0

    async def generate(self, payload):
        self.calls += 1
        return await FakeHandoverProvider().generate(payload)


def test_valid_request_returns_internal_content():
    provider = SpyProvider()
    gateway = HandoverGateway(provider=provider)
    input = make_input()

    result = asyncio.run(gateway.generate(input=input))

    assert provider.calls == 1
    assert result.sections
    assert result.coverage_complete is False
    assert result.sections[0].claims[0].sources == (input.retrieval.evidence.shift_records[0].reference,)
    assert set(input.metrics.warnings).issubset(result.warnings)


def test_invalid_scope_never_calls_provider():
    provider = SpyProvider()
    gateway = HandoverGateway(provider=provider)
    input = make_input()

    input = input.model_copy(
        update={"execution_context": input.execution_context.model_copy(update={"permissions": frozenset()})}
    )

    with pytest.raises(InternalInputValidationError):
        asyncio.run(gateway.generate(input=input))

    assert provider.calls == 0


def test_unreviewed_text_never_calls_provider():
    provider = SpyProvider()
    gateway = HandoverGateway(provider=provider)

    with pytest.raises(PrivacyRejected):
        asyncio.run(gateway.generate(input=with_notes("Mary Smith drank water")))

    assert provider.calls == 0


def test_provider_timeout():
    class WaitingProvider:
        async def generate(self, payload):
            await asyncio.Event().wait()

    gateway = HandoverGateway(
        provider=WaitingProvider(),
        provider_timeout_seconds=0.01,
    )

    with pytest.raises(HandoverProviderTimeout):
        asyncio.run(gateway.generate(input=make_input()))


def test_provider_exception_is_sanitised():
    class FailingProvider:
        async def generate(self, payload):
            raise RuntimeError("PRIVATE_RESPONSE_MARKER")

    gateway = HandoverGateway(provider=FailingProvider())

    with pytest.raises(HandoverProviderError) as caught:
        asyncio.run(gateway.generate(input=make_input()))

    assert str(caught.value) == "Handover provider failed"
    assert "PRIVATE_RESPONSE_MARKER" not in str(caught.value)
    assert caught.value.__suppress_context__ is True


def test_caller_cancellation_propagates():
    async def exercise():
        entered = asyncio.Event()

        class WaitingProvider:
            async def generate(self, payload):
                entered.set()
                await asyncio.Event().wait()

        gateway = HandoverGateway(provider=WaitingProvider())

        task = asyncio.create_task(gateway.generate(input=make_input()))

        await entered.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())


def test_fabricated_source_is_rejected():
    class CorruptProvider:
        async def generate(self, payload):
            output = await FakeHandoverProvider().generate(payload)

            bad_claim = output.claims[0].model_copy(update={"source_aliases": ("SRC_999",)})

            return output.model_copy(update={"claims": (bad_claim,)})

    gateway = HandoverGateway(provider=CorruptProvider())

    with pytest.raises(InboundValidationError):
        asyncio.run(gateway.generate(input=make_input()))


def test_unexpected_provider_return_type_is_rejected():
    class WrongTypeProvider:
        async def generate(self, payload):
            return {"claims": []}

    gateway = HandoverGateway(provider=WrongTypeProvider())

    with pytest.raises(InboundValidationError):
        asyncio.run(gateway.generate(input=make_input()))


@pytest.mark.parametrize(
    "timeout",
    [0, -1, float("inf"), float("nan")],
)
def test_invalid_timeout_configuration(timeout):
    with pytest.raises(ValueError):
        HandoverGateway(
            provider=FakeHandoverProvider(),
            provider_timeout_seconds=timeout,
        )
