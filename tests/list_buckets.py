import os
import json
from google.cloud import storage

def list_buckets(project_id, key_path):
    storage_client = storage.Client.from_service_account_json(key_path)
    buckets = list(storage_client.list_buckets(project=project_id))
    
    if not buckets:
        print("No buckets found in project.")
    else:
        print("Buckets found:")
        for bucket in buckets:
            print(f" - {bucket.name}")

if __name__ == "__main__":
    project_id = "ee-dikoharyadhanto74"
    key_path = r"C:\Users\dikoh\Documents\Google\.config\ee-dikoharyadhanto74-5d6e188dec7b.json"
    
    try:
        list_buckets(project_id, key_path)
    except Exception as e:
        print(f"Error: {e}")
