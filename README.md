# **Audit Pit Crew \- GitHub Repository Security Scanner**

The Audit Pit Crew is a multi-container application designed to perform automated security scans (using tools like Slither) on Solidity smart contract repositories whenever a new Pull Request is opened or synchronized on GitHub.

The architecture uses **FastAPI** for the Webhook API, **Redis** as the Celery message broker, and a dedicated **Celery Worker** for asynchronous, resource-intensive scanning tasks.

## **🚀 Getting Started**

These instructions will get your Dockerized system up and running for development and testing.

### **Prerequisites**

* Docker and Docker Compose installed.  
* A GitHub Personal Access Token (PAT) with repo scope (or an installed GitHub App token, if you are beyond the MVP stage) for cloning private repositories and reporting results.

### **Installation**

1. **Clone the Repository**  
   git clone \[https://github.com/your-username/audit-pit-crew.git\](https://github.com/your-username/audit-pit-crew.git)  
   cd audit-pit-crew

2. Configure Environment Variables  
   Create a file named .env in the root directory. This file must contain the following variables:  
   \# API Settings  
   APP\_NAME=Audit-Pit-Crew

   \# GitHub Webhook Security  
   \# MUST be a strong, random string that you will also configure in GitHub's webhook settings.  
   GITHUB\_WEBHOOK\_SECRET=a\_very\_secure\_random\_string\_here

   \# Redis Configuration (Used by Celery)  
   REDIS\_HOST=audit\_pit\_redis  
   REDIS\_PORT=6379

3. Build and Run the Containers  
   Start all services (API, Redis, Worker) using Docker Compose:  
   sudo docker compose up \--build

   The system is ready when you see logs confirming that the audit\_pit\_api is running on http://0.0.0.0:8000 and the audit\_pit\_worker is connected to Redis.

## **🔗 Webhook Integration & End-to-End Testing**

To test the entire pipeline (API signature verification, task queuing, worker execution, and reporting), you must configure a GitHub Webhook and trigger it with a Pull Request.

### **Step 1: Expose Your Local API**

Since your Docker service runs locally, GitHub cannot reach it directly. You must use a tunneling service like **ngrok** to create a public URL.

1. Install ngrok (if you haven't already).  
2. Run the tunnel:  
   ngrok http 8000

3. **Copy the public HTTPS URL** (e.g., https://a1b2c3d4e5f6.ngrok-free.app).

### **Step 2: Configure the GitHub Webhook**

1. Go to the repository where you want to test the scanner.  
2. Navigate to **Settings** \> **Webhooks** \> **Add webhook**.

| Setting | Value |
| :---- | :---- |
| **Payload URL** | Paste the ngrok HTTPS URL, followed by your endpoint: https://\<YOUR\_NGROK\_URL\>/webhook/github |
| **Content type** | Select **application/json** (This is the required format) |
| **Secret** | Enter the exact value from your .env file: GITHUB\_WEBHOOK\_SECRET |
| **Which events should trigger this webhook?** | Select **"Let me select individual events"** and choose only **"Pull requests"**. |
| **Active** | Ensure this box is checked. |

3. Click **"Add webhook"**.

### **Step 3: Trigger the End-to-End Test**

Now, you can perform the full test:

1. Ensure your Docker logs are running (sudo docker compose up).  
2. **In the configured GitHub repository, create a new branch and open a Pull Request.**

#### **Expected Log Sequence (Success)**

Monitor your Docker terminal for the following sequence, which confirms your entire multi-container architecture is working:

| Service | Log Message | Meaning |
| :---- | :---- | :---- |
| audit\_pit\_api | INFO: "POST /webhook/github HTTP/1.1" 202 Accepted | API received and validated the webhook, and queued the task. |
| audit\_pit\_worker | Task scan\_repo\_task\[...\] received | Worker picked up the task from the Redis queue. |
| audit\_pit\_worker | ✅ Clone successful. | Repository was cloned into the workspace. |
| audit\_pit\_worker | 🔍 Starting Slither scan... | Scanning process initiated. |
| audit\_pit\_worker | ℹ️ \[Task ...\] Skipping GitHub posting (No issues found...) | Worker successfully checked for issues and skipped reporting because none were found. (If issues are found, it will attempt to post the report.) |
| audit\_pit\_worker | Task scan\_repo\_task\[...\] succeeded... | Task completed cleanly. |

If this sequence runs without raising a TypeError (the bug we fixed) or a signature mismatch error, your webhook integration is robust and ready for development.