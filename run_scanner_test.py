import os
from src.core.analysis.scanner import SlitherScanner

# Get absolute path to the temp folder
target = os.path.abspath("temp_scan")

print(f"🚀 Testing Scanner on: {target}")

scanner = SlitherScanner()
issues = scanner.run(target)

print("\n---------------- REPORT ----------------")
if issues:
    for i, issue in enumerate(issues):
        print(f"{i+1}. [{issue['severity']}] {issue['type']}")
        print(f"   File: {issue['file']} (Line {issue['line']})")
else:
    print("No High/Medium issues found (or scanner failed).")
print("----------------------------------------")