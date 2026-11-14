from celery import Celery
from app.config import settings
from app.services import jobs

celery = Celery("opportunityos", broker=settings.redis_url)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.jobs_eager,
    task_time_limit=540,
    task_soft_time_limit=510,
    beat_schedule={
        "outbox": {"task": "outbox", "schedule": 10.0},
        "recovery": {"task": "recovery", "schedule": 60.0},
        "reminders": {"task": "reminders", "schedule": 3600.0},
        "verification_refresh": {"task": "verification_refresh", "schedule": 86400.0},
    },
)


@celery.task(name="execute_job")
def execute_job(job_id):
    jobs.execute(job_id)


@celery.task(name="outbox")
def outbox():
    jobs.dispatch()


@celery.task(name="recovery")
def recovery():
    jobs.recover()


@celery.task(name="reminders")
def reminders():
    from app.services.notifications import reminders as deliver

    deliver()


@celery.task(name="verification_refresh")
def verification_refresh():
    from app.services.verification_refresh import refresh

    refresh()
