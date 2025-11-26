
import hmac
import hashlib
import json
import uvicorn
import logging
import time
import jwt
import requests
from fastapi import FastAPI, Request, HTTPException, Depends, status
from typing import Dict, Any
from src.config import settings
from src.worker.tasks import scan_repo_task

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
    
    # 🌟 FIX: Initialize 'action' so it is available to the final return statement
    action = None

    # 1. Listen for PR events only
    if event_type == "pull_request":
        action = payload.get("action")
        
        # We want to scan when a PR is opened or new commits are pushed (synchronize)
        if action in ["opened", "synchronize"]:
            repo_url = payload["repository"]["clone_url"]
            # 1. Generate a JWT for the GitHub App
            with open(settings.GITHUB_PRIVATE_KEY_PATH, 'r') as pem_file:
                private_key = pem_file.read()

            now = int(time.time())
            payload_jwt = {
                'iat': now - 60,
                'exp': now + (10 * 60),
                'iss': settings.GITHUB_APP_ID
            }
            encoded_jwt = jwt.encode(payload_jwt, private_key, algorithm='RS256')

            # 2. Get installation ID for the repo
            repo_owner = payload['repository']['owner']['login']
            repo_name = payload['repository']['name']
            headers = {
                'Authorization': f'Bearer {encoded_jwt}',
                'Accept': 'application/vnd.github+json'
            }
            installation_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/installation"
            installation_resp = requests.get(installation_url, headers=headers)
            if installation_resp.status_code != 200:
                logger.error(f"Failed to get installation ID: {installation_resp.text}")
                raise HTTPException(status_code=500, detail="Failed to get GitHub App installation ID")
            installation_id = installation_resp.json()['id']

            # 3. Create installation access token
            access_token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
            access_token_resp = requests.post(access_token_url, headers=headers)
            if access_token_resp.status_code != 201:
                logger.error(f"Failed to get installation access token: {access_token_resp.text}")
                raise HTTPException(status_code=500, detail="Failed to get GitHub App installation token")
            access_token = access_token_resp.json()['token']

            # 4. Hand off the job to the Worker
            logger.info(f"➡️ Webhook received. Queuing scan for {repo_url}")
            scan_repo_task.delay(
                repo_url=repo_url,
                token=access_token,
                pr_context={
                    'owner': repo_owner,
                    'repo': repo_name,
                    'pr_number': payload['pull_request']['number']
                }
            )
            
            # 3. Return fast response to GitHub (CRITICAL)
            return {"status": "queued", "repo": repo_url}

    # Ignore other events (push, commit, issues, etc.)
    # This now safely uses 'action' which is initialized to None if not a PR event.
    return {"status": "ignored", "message": f"Event type {event_type} or action {action} ignored"}

# --- Running the Server (For local testing) ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    