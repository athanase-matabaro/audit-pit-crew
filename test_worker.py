from src.worker.tasks import scan_repo_task
import time
import os

# Point to your local vulnerable repo again
current_dir = os.getcwd()
TEST_REPO = os.path.join(current_dir, "temp_scan")

print("📨 Sending task to Celery/Redis...")

# .delay() is the magic command that sends it to the background
task = scan_repo_task.delay(repo_url=TEST_REPO, token=None)

print(f"🆔 Task ID: {task.id}")
print("⏳ Waiting for worker to finish (polling)...")

# Wait for result
while not task.ready():
    time.sleep(1)
    print(".", end="", flush=True)

print("\n✅ Task Finished!")
result = task.get()

print("---------------- WORKER RESULT ----------------")
print(f"Status: {result['status']}")
print(f"Issues Found: {result['issues_count']}")
print("-----------------------------------------------")