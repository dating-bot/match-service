from celery import Celery
from celery.schedules import crontab

from match_service.infra.tracing import setup_tracing

setup_tracing(service_name="match-service-celery")

celery_app = Celery(
    "match_service",
    broker="redis://valkey:6379/2",
    include=[
        "match_service.app.tasks.outbox_poller",
        "match_service.app.tasks.flush_match_activity",
        "match_service.app.tasks.check_ghosted_matches",
    ],
)

celery_app.conf.beat_schedule = {
    "outbox_poller": {
        "task": "match_service.app.tasks.outbox_poller.outbox_poller",
        "schedule": 2.0,
    },
    "flush_match_activity": {
        "task": "match_service.app.tasks.flush_match_activity.flush_match_activity",
        "schedule": 60.0,
    },
    "check_ghosted_matches": {
        "task": "match_service.app.tasks.check_ghosted_matches.check_ghosted_matches",
        "schedule": crontab(hour=12, minute=0),
    },
}

celery_app.conf.timezone = "UTC"
