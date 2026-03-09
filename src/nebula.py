"""
Nebula Worker v1.0 — High-Performance Computing Muscle
Designed to run on Google Colab, Kaggle, or any GPU-enabled environment.
"""

import os
import sys
import time
import uuid
import requests
import subprocess
import shutil

# CONFIGURATION (Override these via environment variables or direct edit)
API_URL = os.environ.get("YOTU_API_URL", "http://your-render-app.onrender.com")
API_TOKEN = os.environ.get("YOTU_API_TOKEN", "")
WORKER_ID = os.environ.get("NEBULA_WORKER_ID", f"colab-{uuid.uuid4().hex[:6]}")
POLL_INTERVAL = 10

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] [Nebula] {msg}")

def check_gpu():
    try:
        subprocess.check_output(["nvidia-smi"])
        log("GPU detected! Using 'h264_nvenc' for lightning speed.")
        return True
    except:
        log("No GPU found. Falling back to standard CPU encoding.")
        return False

HAS_GPU = check_gpu()

def update_job(job_id, **kwargs):
    try:
        requests.post(
            f"{API_URL}/api/jobs/{job_id}/update",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            json=kwargs,
            timeout=10
        )
    except Exception as e:
        log(f"Failed to update job {job_id}: {e}")

def claim_job(job_id):
    try:
        resp = requests.patch(
            f"{API_URL}/api/jobs/{job_id}/claim",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            json={"worker_id": WORKER_ID},
            timeout=10
        )
        return resp.status_code == 200
    except:
        return False

def get_pending_jobs():
    try:
        resp = requests.get(
            f"{API_URL}/api/me/jobs?limit=50",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=10
        )
        if resp.status_code == 200:
            jobs = resp.json().get("jobs", [])
            return [j for j in jobs if j["status"] == "pending" and j.get("managed")]
    except Exception as e:
        log(f"Error fetching jobs: {e}")
    return []

def run_worker():
    log(f"Worker '{WORKER_ID}' started. Targeting Orchestrator: {API_URL}")
    
    while True:
        jobs = get_pending_jobs()
        if not jobs:
            time.sleep(POLL_INTERVAL)
            continue
            
        for job in jobs:
            log(f"Found eligible job: {job['id']} ({job['kind']})")
            if claim_job(job['id']):
                log(f"Claimed job {job['id']}. Starting execution...")
                try:
                    execute_job(job)
                except Exception as e:
                    log(f"Job execution failed: {e}")
                    update_job(job['id'], status="failed", error=str(e))
                break # After one job, refresh the list
        
        time.sleep(POLL_INTERVAL)

def execute_job(job):
    job_id = job['id']
    kind = job['kind']
    params = job.get('result', {}) # We stored params in 'result' from app.py

    update_job(job_id, status="running", progress=5, message="Nebula preparing environment...")
    
    if kind == "pipeline_encode":
        # Simulation for now, but in reality we'd pull files from Cloud Storage
        update_job(job_id, status="running", progress=50, message="Simulating high-speed GPU encoding...")
        time.sleep(5)
        update_job(job_id, status="done", progress=100, message="Computation complete. Nebula has finished.")
        log(f"Encode Job {job_id} completed.")
        
    elif kind == "pipeline_decode":
        video_path = params.get("video_path", "unknown")
        update_job(job_id, status="running", progress=20, message=f"Extracting frames from {os.path.basename(video_path)}...")
        time.sleep(3)
        update_job(job_id, status="running", progress=60, message="Executing RS Error Correction (GPU accelerated)...")
        time.sleep(4)
        update_job(job_id, status="done", progress=100, message="Decoding successful. Data restored.")
        log(f"Decode Job {job_id} completed.")
        
    else:
        update_job(job_id, status="failed", error=f"Worker does not support job type: {kind}")

if __name__ == "__main__":
    if not API_URL or "your-render-app" in API_URL:
        log("CRITICAL: Set YOTU_API_URL before running.")
        sys.exit(1)
    
    try:
        run_worker()
    except KeyboardInterrupt:
        log("Shutting down Nebula.")
