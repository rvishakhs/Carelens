from redis.asyncio import Redis
from app.shared.telemetry import get_logger

logger = get_logger(__name__)

_redis: Redis | None = None


def init_redis(redis_url: str) -> Redis:
    global _redis

    _redis = Redis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
    )

    return _redis


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError(
            "Redis not initialised; call init_redis() at startup"
        )

    return _redis

async def check_redis() -> bool:
    redis = get_redis()

    try:
        return bool(await redis.ping())
    except Exception:
        logger.exception("redis_health_check_failed")
        return False


async def close_redis() -> None:
    global _redis

    if _redis is not None:
        await _redis.aclose()
        _redis = None