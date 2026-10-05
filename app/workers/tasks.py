import time
from app.workers.celery_app import celery_app

@celery_app.task(name="debug_heartbeat_task")
def debug_heartbeat_task():
    time.sleep(5)
    return "Heartbeat successful — Celery worker is alive."