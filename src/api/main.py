import hmac
import hashlib
import json
import uvicorn
import logging
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Depends, status, Header
from fastapi.responses import Response
from typing import Dict, Any, Optional
from src.config import settings
from src.worker.tasks import scan_repo_task
from src.core.redis_client import RedisClient
from src.core.reports.pdf_generator import PreAuditReportGenerator, ReportData, IssuesSummary

logger = logging.getLogger(__name__)

# --- Dependencies ---

# Dependency to verify GitHub's signature
async def verify_signature(request: Request):
    """Verifies the webhook signature against the secret."""
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()
    
    # ==================================================================
    # 🛡️ LOCAL DEBUG BYPASS (Header-Based)
    # Allows curl/manual requests without a signature header to pass.
    # This works even if GITHUB_WEBHOOK_SECRET is set in .env.
    # ==================================================================
    if signature is None:
        logger.warning("⚠️ Local Test: Signature header missing. Bypassing security check.")
        return body
    # ==================================================================

    # Normal Security Logic
    if not settings.GITHUB_WEBHOOK_SECRET:
         logger.error("❌ Webhook secret not configured.")
         raise HTTPException(status_code=500, detail="Server misconfiguration")

    secret_bytes = settings.GITHUB_WEBHOOK_SECRET.encode('utf-8')
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
    x_github_event: Optional[str] = Header(None),
    body: bytes = Depends(verify_signature)
):
    """
    Handles all incoming GitHub Webhook events.
    """
    payload: Dict[str, Any] = json.loads(body.decode('utf-8'))
    action = payload.get("action")

    # 1. Validation and Event Filtering
    if x_github_event != "pull_request":
        logger.info(f"Skipping webhook event: {x_github_event}")
        return {"message": f"Event '{x_github_event}' received but skipped."}

    # Process only relevant PR actions
    if action not in ["opened", "reopened", "synchronize"]:
        logger.info(f"Skipping pull_request action: {action}")
        return {"message": f"PR action '{action}' received but skipped."}

    try:
        # 2. Extract Context
        pr_context = {
            "owner": payload["repository"]["owner"]["login"],
            "repo": payload["repository"]["name"],
            "pr_number": payload["pull_request"]["number"],
            "base_sha": payload["pull_request"]["base"]["sha"],
            "head_sha": payload["pull_request"]["head"]["sha"],
            "base_ref": payload["pull_request"]["base"]["ref"],
            "head_ref": payload["pull_request"]["head"]["ref"],
            "installation_id": payload["installation"]["id"]
        }

        import re
        repo_url = payload["repository"]["clone_url"]
        # Remove markdown formatting if present (defensive)
        repo_url = re.sub(r'^\[([^\]]+)\]\([^\)]+\)$', r'\1', repo_url)

        # 3. Dispatch Celery Task
        task_id = scan_repo_task.delay(repo_url, pr_context)
        logger.info(f"Received PR #{pr_context['pr_number']}. Task dispatched: {task_id}")

        return {
            "message": "Webhook received and task dispatched.", 
            "task_id": str(task_id)
        }

    except KeyError as e:
        logger.error(f"Missing required field in GitHub payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: Missing key {e}")

    except Exception as e:
        logger.error(f"Failed to process webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during task dispatch.")


@app.get("/api/reports/{owner}/{repo}/pdf")
async def get_pre_audit_pdf(owner: str, repo: str):
    """
    Generate and download a Pre-Audit Clearance Certificate PDF.
    
    Retrieves the latest scan results for the repository and generates
    a professional PDF report suitable for sharing with investors.
    
    Args:
        owner: Repository owner/organization name
        repo: Repository name
        
    Returns:
        PDF file as downloadable response
        
    Raises:
        404: No scan results found for this repository
        500: PDF generation failed
    """
    logger.info(f"📄 PDF report requested for {owner}/{repo}")
    
    # Retrieve scan results from Redis
    redis_client = RedisClient()
    scan_result = redis_client.get_scan_result(owner, repo)
    
    if not scan_result:
        logger.warning(f"⚠️ No scan results found for {owner}/{repo}")
        raise HTTPException(
            status_code=404,
            detail=f"No scan results found for {owner}/{repo}. Run a security scan first."
        )
    
    try:
        # Parse issues and count by severity
        issues = scan_result.get("issues", [])
        issues_summary = IssuesSummary()
        
        for issue in issues:
            severity = issue.get("severity", "informational").lower()
            if severity == "critical":
                issues_summary.critical += 1
            elif severity == "high":
                issues_summary.high += 1
            elif severity == "medium":
                issues_summary.medium += 1
            elif severity == "low":
                issues_summary.low += 1
            else:
                issues_summary.informational += 1
        
        # Parse scan date
        saved_at = scan_result.get("saved_at", datetime.utcnow().isoformat())
        try:
            scan_date = datetime.fromisoformat(saved_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            scan_date = datetime.utcnow()
        
        # Build report data
        report_data = ReportData(
            repo_owner=owner,
            repo_name=repo,
            scan_date=scan_date,
            commit_sha=scan_result.get("commit_sha", "unknown"),
            branch=scan_result.get("branch", "main"),
            tools_used=scan_result.get("tools_used", ["Slither", "Mythril"]),
            issues_summary=issues_summary,
            issues=issues,
            files_scanned=scan_result.get("files_scanned", 0),
        )
        
        # Generate PDF
        generator = PreAuditReportGenerator()
        pdf_bytes = generator.generate(report_data)
        
        # Generate filename
        date_str = scan_date.strftime("%Y%m%d")
        filename = f"{owner}_{repo}_pre_audit_certificate_{date_str}.pdf"
        
        logger.info(f"✅ Generated PDF report for {owner}/{repo}: {len(pdf_bytes)} bytes")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Scan-Date": saved_at,
                "X-Issues-Total": str(issues_summary.total),
                "X-Clearance-Status": "PASSED" if issues_summary.blocking == 0 else "FAILED",
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to generate PDF report: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF report: {str(e)}"
        )


@app.get("/api/reports/{owner}/{repo}/summary")
async def get_scan_summary(owner: str, repo: str):
    """
    Get a summary of the latest scan results for a repository.
    
    This endpoint returns JSON summary data that can be used to display
    scan status in dashboards or check if PDF generation is available.
    
    Args:
        owner: Repository owner/organization name
        repo: Repository name
        
    Returns:
        JSON summary of scan results
    """
    redis_client = RedisClient()
    scan_result = redis_client.get_scan_result(owner, repo)
    
    if not scan_result:
        raise HTTPException(
            status_code=404,
            detail=f"No scan results found for {owner}/{repo}."
        )
    
    # Count issues by severity
    issues = scan_result.get("issues", [])
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0}
    
    for issue in issues:
        severity = issue.get("severity", "informational").lower()
        if severity in severity_counts:
            severity_counts[severity] += 1
        else:
            severity_counts["informational"] += 1
    
    blocking_count = severity_counts["critical"] + severity_counts["high"]
    
    return {
        "repository": f"{owner}/{repo}",
        "scan_date": scan_result.get("saved_at"),
        "scan_type": scan_result.get("scan_type", "unknown"),
        "branch": scan_result.get("branch", "unknown"),
        "commit_sha": scan_result.get("commit_sha", "unknown"),
        "tools_used": scan_result.get("tools_used", []),
        "files_scanned": scan_result.get("files_scanned", 0),
        "issues": {
            "total": len(issues),
            "by_severity": severity_counts,
            "blocking": blocking_count,
        },
        "clearance_status": "PASSED" if blocking_count == 0 else "FAILED",
        "pdf_available": True,
    }


# --- Running the Server (For local testing) ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")