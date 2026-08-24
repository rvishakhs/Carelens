
from app.modules.residents.models import Resident, ResidentStatus


async def seed_home_a_resident(session, home_id):
    resident = Resident(
        care_home_id=home_id,
        first_name="John",
        last_name="Smith",
        status= ResidentStatus.ACTIVE,
    )

    session.add(resident)
    await session.commit()

    return resident

async def seed_home_b_resident(session, home_id):

    resident = Resident(
        care_home_id=home_id,
        first_name="John",
        last_name="Smith",
        status= ResidentStatus.ACTIVE,
    )

    session.add(resident)
    await session.commit()

    return resident