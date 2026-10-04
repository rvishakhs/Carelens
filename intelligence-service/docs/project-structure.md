# Intelligence service structure

The independent service remains inside the CareLens repository. This restructure
is limited to the intelligence service; it does not move CareLens application tests.

```text
intelligence-service/
  src/intelligence/
    api/              HTTP requests and application composition
    agents/           use-case agents
    connectors/       scoped CareLens data access and normalisation
    core/             common contracts, ports, errors and scope policy
    handover/         domain contracts, evidence, metrics, rendering and validation
    gateway/          privacy boundary, preparation, output validation and orchestration
    providers/        implementations of gateway provider protocols
      fake_demo.py       legacy fluid-demo adapter
      fake_handover.py   offline handover adapter
      openai_handover.py existing unfinished external-provider adapter
    workflow/         resident job execution
    tasks/            Celery task entry points
    workers/          Celery application configuration
    dispatcher/       outbox dispatch
    persistence/      database models and repositories
  tests/              unit, architecture, integration and shared support
  migrations/         schema changes
  scripts/            explicit operational and development utilities
  docs/               design and implementation guides
```

Provider protocols and wire contracts remain in `gateway/contracts.py`. Only the
`providers/` package may import model SDKs; the architecture tests enforce this.
API/worker composition selects adapters, while gateway/domain logic depends on
protocols. The service may call CareLens over its connector but cannot import the
CareLens `app` package.

Shared test builders now live in `tests/support/`. The canonical retrieval envelope
is `handover/contracts.py:HandoverRetrieval`; an unused duplicate dataclass was
removed from evidence.py. The connector still returns ShiftEvidence; envelope
construction belongs to the workflow, not the provider.

## Before switching to OpenAI

The adapter was moved, not completed or exercised against the API. Synthetic startup
uses fake adapters until external-provider configuration and lifecycle are finished.
The legacy fake adapter remains because existing demo routes still depend on it.

Next integration work must address:

1. Explicit provider/model configuration and credential handling; instantiate and
   close the external client only when that provider is selected.
2. Mocked adapter tests for successful output, refusals/incomplete results, malformed
   output, timeouts and cancellation; keep the fake adapter for reproducible tests.
3. The current gateway permits exact extractive claims only. The existing provider
   prompt requests narrative claims, so successful API parsing alone will not make
   output acceptable to the gateway. Align those behaviours before live testing.
4. ReviewedTextPolicy is a fail-closed manual text boundary, not automatic identity
   removal. Do not replace it with an unreviewed passthrough for real records.
5. Live model checks must be separately opt-in, using synthetic data first. Clinical
   review and data-processing approvals remain separate from code/test readiness.

No Celery scheduling, durable draft completion or clinical approval behaviour was
added by this structural change.
