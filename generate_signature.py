import hmac
import hashlib
import json
from src.config import settings

# --- INPUTS ---
LOCAL_REPO_PATH = "/home/athanase-matabaro/Dev/audit-pit-crew/temp_scan"

# Create the payload dictionary first (cleaner than string concatenation)
payload_dict = {
    "action": "opened",
    "repository": {
        "clone_url": LOCAL_REPO_PATH,
        "full_name": "your/test-repo" # Used for context
    },
    "pull_request": {
        "number": 1, 
        "head": {"repo": {"owner": {"login": "your"}, "name": "test-repo"}}
    }
}

# IMPORTANT: GitHub sends JSON without any pretty printing or indentation.
# This ensures the payload string is clean and compact for hashing.
PAYLOAD_STRING = json.dumps(payload_dict, separators=(',', ':'))

# --- CALCULATION ---
SECRET = settings.GITHUB_WEBHOOK_SECRET

secret_bytes = SECRET.encode('utf-8')
body_bytes = PAYLOAD_STRING.encode('utf-8')

# Calculate the HMAC-SHA256 hash
hash_object = hmac.new(secret_bytes, body_bytes, hashlib.sha256)
calculated_signature = "sha256=" + hash_object.hexdigest()

# Write the exact payload string to a file for curl to use
with open("payload.json", "w") as f:
    f.write(PAYLOAD_STRING)


print("--- NEW SIGNATURE GENERATED ---")
print(f"Payload (written to payload.json): {PAYLOAD_STRING}")
print(f"✅ Calculated Signature for testing:")
print(calculated_signature)