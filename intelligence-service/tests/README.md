# Intelligence service tests

Run commands from `intelligence-service/`, using its virtual environment.
The CareLens application's root `tests/` directory is a separate suite.

```text
tests/
  architecture/       dependency boundaries and test-module independence
  unit/
    api/              synthetic API; database probe replaced in tests
    connectors/       CareLens HTTP transport mocked with httpx.MockTransport
    gateway/          privacy, aliases, validation, stage composition, orchestration
    handover/         rendering, evidence, retrieval, input validation, metrics
    test_config.py
  integration/
    persistence/      PostgreSQL submission, job/outbox claims and tenant isolation
    workflow/         database-backed execution/claim loading
  support/            reusable synthetic builders and opt-in database harness
```

Fast offline suite (no model API, Redis, PostgreSQL or real clinical data):

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --confcutdir=tests -p no:cacheprovider tests/unit tests/architecture -q
```

Collect/run all tests while explicitly disabling database execution:

```sh
INTELLIGENCE_RUN_DB_TESTS=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --confcutdir=tests -p no:cacheprovider -q
```

Database tests require a separately prepared disposable local PostgreSQL instance,
migrations and runtime-role credentials. Enable them deliberately:

```sh
INTELLIGENCE_RUN_DB_TESTS=1 .venv/bin/python -m pytest --confcutdir=tests tests/integration -q
```

Do not use production data or a privileged migration role. The concurrency test
has a dedicated setup script at `scripts/test_outbox_concurrency.py`; read its
prerequisites before running it.

## Adding tests

- Mirror the responsible source package under `unit/`.
- Put shared builders in `support/`; do not import another `test_*.py` module.
- Mock external services in unit tests. An SDK adapter's tests should go in
  `unit/providers/` when that integration is implemented.
- Keep real service tests under `integration/`, marked `integration` and explicitly
  opt-in. A future live model test must have its own opt-in switch; never run paid
  requests implicitly in the offline suite.
- Keep clinical acceptance cases and human review results distinct from passing
  software tests. The gateway currently accepts only deterministic extractive text.
