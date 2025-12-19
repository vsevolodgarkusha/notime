from celery import Celery
import os

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

app = Celery(
    "tasks",
    broker=f"redis://{REDIS_HOST}:6379/0",
    backend=f"redis://{REDIS_HOST}:6379/0",
    include=["app.tasks"],
)

app.conf.beat_schedule = {
    'check-due-tasks-every-minute': {
        'task': 'app.tasks.check_due_tasks',
        'schedule': 60.0,
    },
}

if __name__ == "__main__":
    app.start()
