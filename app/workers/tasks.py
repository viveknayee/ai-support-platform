import asyncio                                                        
import time
import uuid                                                           
from app.services.document_processor import process_document        
from app.workers.celery_app import celery_app


@celery_app.task(name="debug_heartbeat_task")
def debug_heartbeat_task():
    time.sleep(5)
    return "Heartbeat successful — Celery worker is alive."


@celery_app.task(name="process_document_task", ignore_result=True)                 
def process_document_task(document_id: str, tenant_id: str) -> str:  
    return asyncio.run(process_document(uuid.UUID(document_id), uuid.UUID(tenant_id)))   