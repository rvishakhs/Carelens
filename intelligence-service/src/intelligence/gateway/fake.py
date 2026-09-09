from intelligence.gateway.contracts import ProviderOutput, SafePayload


class FakeProvider:
    async def generate(self, payload: SafePayload) -> ProviderOutput:
        metrics = [("consumed_ml", payload.consumed_ml), ("offered_ml", payload.offered_ml)]
        if not payload.source_aliases:
            metrics = [("no_records", None)]
        return ProviderOutput.model_validate(
            {
                "claims": [
                    {
                        "resident_alias": payload.resident_alias,
                        "source_aliases": payload.source_aliases,
                        "metric": metric,
                        "value": value,
                    }
                    for metric, value in metrics
                ]
            }
        )
