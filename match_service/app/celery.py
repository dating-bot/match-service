from celery import Celery

celery_app = Celery(
    "match_service",
    broker="redis://localhost:6379/0",
    include=["match_service.app.tasks.outbox_poller"],
)

celery_app.conf.beat_schedule = {
    "outbox_poller": {
        "task": "match_service.app.tasks.outbox_poller.outbox_poller",
        "schedule": 2.0,
    },
}

celery_app.conf.timezone = "UTC"
