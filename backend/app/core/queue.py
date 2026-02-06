"""Redis queue for background jobs. Returns None if Redis not configured."""
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from rq import Queue

_queue: "Queue | None" = None


def get_queue() -> "Queue | None":
    global _queue
    if _queue is not None:
        return _queue
    if not settings.redis_url:
        return None
    from redis import Redis
    from rq import Queue
    conn = Redis.from_url(settings.redis_url)
    _queue = Queue("default", connection=conn)
    return _queue
