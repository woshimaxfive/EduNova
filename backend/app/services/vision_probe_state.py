"""Shared proof for the server main model; never a second model connection."""
from redis import Redis
from redis.exceptions import RedisError


class VisionProbeState:
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(
            redis_url, decode_responses=True,
            socket_connect_timeout=0.2, socket_timeout=0.5,
        )

    @staticmethod
    def _key(user_id: int, fingerprint: str) -> str:
        return f"edunova:vision-probe:v1:{user_id}:{fingerprint}"

    def status(self, user_id: int, fingerprint: str) -> str:
        try:
            value = self.redis.get(self._key(user_id, fingerprint))
            return value if value in {"verified", "unavailable"} else "unverified"
        except RedisError:
            return "unverified"

    def record(self, user_id: int, fingerprint: str, ok: bool) -> bool:
        try:
            return bool(self.redis.set(
                self._key(user_id, fingerprint),
                "verified" if ok else "unavailable",
                ex=604800 if ok else 3600,
            ))
        except RedisError:
            return False
