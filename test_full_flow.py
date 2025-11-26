from src.core.git_manager import GitManager
from src.core.analysis.scanner import SlitherScanner
import os

# 1. Setup
git = GitManager()
scanner = SlitherScanner()

# POINT THIS TO YOUR LOCAL REPO
# This simulates a "Remote URL" but points to your hard drive
current_dir = os.getcwd()
TEST_REPO = os.path.join(current_dir, "temp_scan")

print("🚀 Starting Integration Test (Local Simulation)...")
print(f"🎯 Target Repo: {TEST_REPO}")

# 2. Create Workspace (The clean room)
path = git.create_workspace()

try:
    # 3. Clone
    # This acts exactly like cloning from GitHub, but faster
    git.clone_repo(path, TEST_REPO, token=None)
    
    # 4. Scan
    print(f"🔍 Scanning files in: {path}")
    issues = scanner.run(path)
    
    print("\n---------------- RESULTS ----------------")
    print(f"Found {len(issues)} issues")
    
    if len(issues) > 0:
        print("✅ SUCCESS! The pipeline is working.")
        for issue in issues:
            print(f"   -> [{issue['severity']}] {issue['type']} in {issue['file']}")
    else:
        print("❌ FAILED: No bugs found (Check if Vulnerable.sol is in temp_scan)")
    print("-----------------------------------------")

finally:
    # 5. Cleanup
    git.remove_workspace(path)
    
    if not os.path.exists(path):
        print("✅ Cleanup Successful (Folder deleted)")