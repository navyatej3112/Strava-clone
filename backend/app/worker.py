"""RQ worker entrypoint. Run with: rq worker default -c app.worker"""
from redis import Redis
from rq import Worker, Queue, Connection

from app.core.config import settings

redis_url = settings.redis_url or "redis://localhost:6379/0"
redis_conn = Redis.from_url(redis_url)

if __name__ == "__main__":
    with Connection(redis_conn):
        worker = Worker([Queue("default", connection=redis_conn)])
        worker.work()
