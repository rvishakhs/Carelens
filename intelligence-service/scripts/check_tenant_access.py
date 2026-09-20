import asyncio
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from intelligence.config import DatabaseSettings


async def main() -> None:
    settings = DatabaseSettings()

    # Use the same database account as FastAPI.
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        hide_parameters=True,
    )

    tenant_a = uuid4()
    tenant_b = uuid4()
    job_id = uuid4()
    actor_id = uuid4()

    job_values = {
        "id": job_id,
        "tenant_id": tenant_a,
        "resident_id": uuid4(),
        "actor_id": actor_id,
        "key": f"access-test-{uuid4()}",
    }

    insert_job = text("""
        INSERT INTO handover_jobs (
            id,
            tenant_id,
            resident_id,
            shift_start,
            shift_end,
            timezone,
            idempotency_key,
            trigger_type,
            requested_by,
            service_identity
        )
        VALUES (
            :id,
            :tenant_id,
            :resident_id,
            TIMESTAMPTZ '2026-01-01 07:00:00+00',
            TIMESTAMPTZ '2026-01-01 19:00:00+00',
            'Europe/London',
            :key,
            'manual',
            :actor_id,
            'tenant-access-test'
        )
    """)

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()

            try:
                role = await connection.scalar(text("SELECT current_user"))
                if role != "intelligence_app":
                    raise RuntimeError("Use the intelligence_app database URL for this test.")
                print("PASS: connected as intelligence_app")

                async def set_tenant(value: str) -> None:
                    await connection.execute(
                        text("""
                            SELECT set_config(
                                'intelligence.tenant_id',
                                :tenant_id,
                                true
                            )
                        """),
                        {"tenant_id": value},
                    )

                async def expect_denied(statement, parameters, label):
                    # A savepoint lets testing continue after an expected error.
                    savepoint = await connection.begin_nested()
                    try:
                        await connection.execute(statement, parameters)
                    except DBAPIError as exc:
                        await savepoint.rollback()
                        sqlstate = getattr(exc.orig, "sqlstate", None)

                        if sqlstate != "42501":
                            raise

                        print(f"PASS: {label}")
                    else:
                        await savepoint.rollback()
                        raise AssertionError(f"Unexpected access: {label}")

                async def visible_count(table: str) -> int:
                    # Table names come only from the fixed calls below.
                    id_column = "id" if table == "handover_jobs" else "job_id"
                    result = await connection.scalar(
                        text(f"SELECT count(*) FROM {table} WHERE {id_column} = :job_id"),
                        {"job_id": job_id},
                    )
                    return int(result)

                # No tenant context: creating a job must fail.
                await set_tenant("")
                await expect_denied(
                    insert_job,
                    job_values,
                    "insert without tenant context rejected",
                )

                # Tenant A can create its own job and request mapping.
                await set_tenant(str(tenant_a))
                await connection.execute(insert_job, job_values)

                await connection.execute(
                    text("""
                        INSERT INTO idempotency_records (
                            tenant_id,
                            actor_id,
                            idempotency_key,
                            request_fingerprint,
                            job_id
                        )
                        VALUES (
                            :tenant_id,
                            :actor_id,
                            :key,
                            :fingerprint,
                            :job_id
                        )
                    """),
                    {
                        "tenant_id": tenant_a,
                        "actor_id": actor_id,
                        "key": f"request-{uuid4()}",
                        "fingerprint": "a" * 64,
                        "job_id": job_id,
                    },
                )

                assert await visible_count("handover_jobs") == 1
                assert await visible_count("idempotency_records") == 1
                print("PASS: tenant A can insert and read its records")

                # Application permissions prohibit changing a saved mapping.
                await expect_denied(
                    text("""
                        UPDATE idempotency_records
                        SET request_fingerprint = :fingerprint
                        WHERE job_id = :job_id
                    """),
                    {"fingerprint": "b" * 64, "job_id": job_id},
                    "idempotency update rejected",
                )

                # Tenant B cannot see tenant A's records.
                await set_tenant(str(tenant_b))
                assert await visible_count("handover_jobs") == 0
                assert await visible_count("idempotency_records") == 0
                print("PASS: tenant B cannot read tenant A's records")

                # Tenant B cannot insert a record belonging to tenant A.
                await expect_denied(
                    insert_job,
                    {
                        **job_values,
                        "id": uuid4(),
                        "key": f"denied-{uuid4()}",
                    },
                    "cross-tenant insert rejected",
                )

                # Existing records are also hidden without tenant context.
                await set_tenant("")
                assert await visible_count("handover_jobs") == 0
                assert await visible_count("idempotency_records") == 0
                print("PASS: records hidden without tenant context")

            finally:
                await transaction.rollback()
                print("Test transaction rolled back; no test records saved.")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
