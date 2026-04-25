import json
import glob
import os

logs = sorted(glob.glob(os.path.expanduser("~/Library/Logs/DiagnosticReports/Python-*.ips")), key=os.path.getmtime, reverse=True)

if not logs:
    print("No crash logs found.")
    exit(1)

log_path = logs[0]
print(f"Analyzing newest log: {log_path}\n")

with open(log_path, 'r') as f:
    lines = f.readlines()

# ips logs often have a JSON header followed by text, or are full JSON.
try:
    header = json.loads(lines[0])
    print(f"Timestamp: {header.get('timestamp')}")
    print(f"Process: {header.get('procName')} [{header.get('pid')}]")
except:
    pass

for line in lines[:50]:
    if "Exception Type:" in line or "Termination Reason:" in line or "Crashed Thread:" in line:
        print(line.strip())

print("\n--- Thread State ---")
capture = False
frames_captured = 0
for line in lines:
    if "Thread " in line and "Crashed:" in line:
        capture = True
        print(line.strip())
        continue
    if capture:
        if line.strip() == "":
            break
        print(line.strip())
        frames_captured += 1
        if frames_captured > 20:
            break
