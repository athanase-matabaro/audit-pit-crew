import hmac
import hashlib
import json
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException, Depends, status
from typing import Dict, Any
from src.config import settings
from src.worker.tasks import scan_repo_task 
from src.core.github_auth import GitHubAuth # Import the new utility

logger = logging.getLogger(__name__)
# Initialize the GitHub Auth utility globally (or as a singleton)
github_auth = GitHubAuth()

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
    
    action = payload.get("action")

    # 1. Listen for PR events ("opened" or "synchronize")
    if event_type == "pull_request" and action in ["opened", "synchronize"]:
        # --- SAFE PAYLOAD EXTRACTION ---
        installation = payload.get("installation")
        if not installation or "id" not in installation:
            logger.error("🛑 'installation' or 'installation.id' missing from webhook payload.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'installation.id' is required but was not found in the payload."
            )
        
        try:
            repo_url = payload["repository"]["clone_url"]
            pr_context = {
                'installation_id': installation["id"], # CRITICAL: Add installation_id
                'owner': payload['repository']['owner']['login'],
                'repo': payload['repository']['name'],
                'pr_number': payload['pull_request']['number'],
                'base_ref': payload['pull_request']['base']['sha'],
                'head_ref': payload['pull_request']['head']['sha'],
            }
        except KeyError as e:
            logger.error(f"🛑 Missing expected key in payload: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing key: {e}")

        # 2. Hand off the job to the Worker
        logger.info(f"➡️ Webhook received. Queuing scan for {pr_context['owner']}/{pr_context['repo']} PR #{pr_context['pr_number']}")
        scan_repo_task.delay(
            repo_url=repo_url, 
            pr_context=pr_context # Pass the complete context
        )
        
        # 3. Return fast response to GitHub (CRITICAL)
        return {"status": "queued", "repo": repo_url}

    # Ignore other events
    ignored_event = f"event={event_type}, action={action}"
    logger.info(f"⚪ Ignoring GitHub event: {ignored_event}")
    return {"status": "ignored", "message": f"Event '{ignored_event}' not configured for scanning."}

# --- Running the Server (For local testing) ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")