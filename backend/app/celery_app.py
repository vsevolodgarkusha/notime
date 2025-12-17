from celery import Celery
import os

# Read the Redis host from the environment variable, defaulting to 'redis' for Docker.
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

app = Celery(
    "tasks",
    broker=f"redis://{REDIS_HOST}:6379/0",
    backend=f"redis://{REDIS_HOST}:6379/0",
    include=["app.tasks"],
)

if __name__ == "__main__":
    app.start()
