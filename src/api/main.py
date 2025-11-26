import hmac
import hashlib
import json
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException, Depends, status
from typing import Dict, Any
from src.config import settings
from src.worker.tasks import scan_repo_task # Import the task we just verified

logger = logging.getLogger(__name__)

# --- Dependencies ---

# Dependency to verify GitHub's signature
async def verify_signature(request: Request):
    """Verifies the webhook signature against the secret."""
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()
    
    # CRITICAL: Do not process if signature is missing
    if not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature missing")

    secret_bytes = settings.GITHUB_WEBHOOK_SECRET.encode('utf-8')
    
    # Calculate the HMAC-SHA256 hash of the request body
    hash_object = hmac.new(secret_bytes, body, hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature mismatch")
        
    return body

# --- API Setup ---

app = FastAPI(title=settings.APP_NAME)

@app.get("/health")
def health_check():
    """Simple endpoint to verify the API is running."""
    return {"status": "ok", "app": settings.APP_NAME}

@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    body: bytes = Depends(verify_signature) # Security check runs first
):
    """
    Handles all incoming GitHub Webhook events.
    """
    event_type = request.headers.get("X-GitHub-Event")
    payload: Dict[str, Any] = json.loads(body.decode('utf-8'))

    # 1. Listen for PR events only
    if event_type == "pull_request":
        action = payload.get("action")
        
        # We want to scan when a PR is opened or new commits are pushed (synchronize)
        if action in ["opened", "synchronize"]:
            repo_url = payload["repository"]["clone_url"]
            # We will generate and retrieve the Installation Token in V2/V3, 
            # for MVP we use a dummy until the worker is integrated.
            
            # 2. Hand off the job to the Worker
            logger.info(f"➡️ Webhook received. Queuing scan for {repo_url}")
            scan_repo_task.delay(
                repo_url=repo_url, 
                token="DUMMY_INSTALLATION_TOKEN" 
            )
            
            # 3. Return fast response to GitHub (CRITICAL)
            return {"status": "queued", "repo": repo_url}

    # Ignore other events (push, commit, issues, etc.)
    return {"status": "ignored", "message": f"Event type {event_type} or action {action} ignored"}

# --- Running the Server (For local testing) ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
