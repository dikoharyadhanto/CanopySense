from celery import Celery
import os

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "canopysense",
    broker=redis_url,
    backend=redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task
def ingest_data_task():
    """
    Background task to trigger GEE ingestion.
    """
    print("Starting GEE ingestion background task...")
    # Trigger ingest_to_postgis logic here
    # mock logic for now
    print("Ingestion task completed successfully.")
    return {"status": "success"}
