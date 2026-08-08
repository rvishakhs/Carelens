"""CLI entrypoint: `uv run synthdata generate --residents 40 --days 90 --seed 42`.

Generation is synchronous (see db.py's docstring), so there's no asyncio here --
this writes directly into the live Postgres schema your Alembic migrations built.
"""

import typer

from app.config import get_settings
from synthdata.generator import generate

app = typer.Typer(help="CareLens synthetic data generator")


@app.callback()
def _callback() -> None:
    """Typer collapses a Typer() app into a single implicit command when it only has
    one @app.command() registered -- this empty callback forces it to keep requiring
    the subcommand name, so `synthdata generate ...` stays valid as more subcommands
    (e.g. a future `reset`) get added."""


@app.command("generate")
def generate_command(
    residents: int = typer.Option(40, "--residents", help="Number of synthetic residents to create"),
    days: int = typer.Option(90, "--days", help="Number of days of history to generate"),
    seed: int = typer.Option(42, "--seed", help="Random seed for reproducibility"),
    care_home_name: str = typer.Option(
        "Meadowbrook House (Synthetic)", "--care-home-name", help="Name for the synthetic care home created by this run"
    ),
    staff_count: int = typer.Option(12, "--staff-count", help="Number of staff user accounts to create"),
    admin_email: str = typer.Option(
        "admin@example-carehome.test", "--admin-email", help="Login email for the sign-in-able bootstrap admin account"
    ),
    admin_password: str | None = typer.Option(
        None,
        "--admin-password",
        help="Temporary password for the bootstrap admin account. Random if not given.",
    ),
    skip_keycloak_admin: bool = typer.Option(
        False,
        "--skip-keycloak-admin",
        help="Only write the admin's local users row -- skip provisioning it in Keycloak (e.g. Keycloak isn't running).",
    ),
) -> None:
    settings = get_settings()
    typer.echo(f"Generating {residents} residents x {days} days for '{care_home_name}' (seed={seed})")

    result = generate(
        database_url=settings.database_url,
        care_home_name=care_home_name,
        residents=residents,
        days=days,
        seed=seed,
        staff_count=staff_count,
        admin_email=admin_email,
        admin_password=admin_password,
        keycloak_server="" if skip_keycloak_admin else settings.KEYCLOAK_SERVER,
        keycloak_realm=settings.KEYCLOAK_REALM,
        keycloak_client_id=settings.KEYCLOAK_CLIENT_ID,
        keycloak_client_secret=settings.keycloak_admin_client_secret,
    )

    typer.echo(f"Done. care_home_id={result.care_home_id}")
    if result.admin_provisioned:
        typer.echo(
            f"Admin login -- email: {result.admin_email}  password: {result.admin_temporary_password}  "
            "(temporary; you'll be prompted to change it on first sign-in)"
        )
    else:
        typer.echo(
            f"Admin row created locally as {result.admin_email} but NOT provisioned in Keycloak "
            "(no KEYCLOAK_SERVER configured or --skip-keycloak-admin was passed) -- it can't sign in yet."
        )


if __name__ == "__main__":
    app()
