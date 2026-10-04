"""Orchestrates one handover generation request."""

import asyncio
import math

from intelligence.gateway.contracts import (
    HandoverOutput,
    HandoverProvider,
)
from intelligence.gateway.preparation import prepare_handover
from intelligence.gateway.privacy import ReviewedTextPolicy
from intelligence.gateway.resolution import resolve_handover
from intelligence.gateway.validation import InboundValidationError
from intelligence.handover.contracts import (
    HandoverAgentInput,
    ValidatedHandoverContent,
)


class HandoverProviderError(RuntimeError):
    """Provider execution failed; contains no provider response data."""


class HandoverProviderTimeout(HandoverProviderError):
    """Provider did not finish within the configured time limit."""


class HandoverGateway:
    def __init__(
        self,
        *,
        provider: HandoverProvider,
        provider_timeout_seconds: float = 30.0,
    ) -> None:
        if (
            not math.isfinite(provider_timeout_seconds)
            or provider_timeout_seconds <= 0
        ):
            raise ValueError(
                "provider_timeout_seconds must be finite and positive"
            )

        self._provider = provider
        self._provider_timeout_seconds = provider_timeout_seconds

    async def generate(
        self,
        *,
        input: HandoverAgentInput,
        text_policy: ReviewedTextPolicy | None = None,
    ) -> ValidatedHandoverContent:
        # Preparation creates fresh aliases for this request and rejects
        # invalid or unapproved content before provider invocation.
        prepared = prepare_handover(
            input=input,
            text_policy=text_policy,
        )

        try:
            async with asyncio.timeout(
                self._provider_timeout_seconds
            ):
                output = await self._provider.generate(
                    prepared.payload
                )

        except asyncio.CancelledError:
            # Preserve caller cancellation, including worker shutdown.
            raise

        except TimeoutError:
            raise HandoverProviderTimeout(
                "Handover provider timed out"
            ) from None

        except Exception:
            # Do not expose SDK errors, response bodies or clinical data.
            raise HandoverProviderError(
                "Handover provider failed"
            ) from None

        # Protocol annotations do not enforce the runtime return type.
        if not isinstance(output, HandoverOutput):
            raise InboundValidationError(
                "Provider returned an unexpected output type"
            )

        # This already performs inbound validation and authorised
        # citation resolution. Avoid duplicating those operations here.
        return resolve_handover(
            prepared=prepared,
            output=output,
        )