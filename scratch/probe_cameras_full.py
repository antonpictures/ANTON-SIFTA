import cv2
import os
from pathlib import Path

out_dir = Path("SwarmEntityWatchingYouTube/camera_probes")
out_dir.mkdir(parents=True, exist_ok=True)

print("Scanning camera indices 0-10...")
for i in range(11):
    cap = cv2.VideoCapture(i)
    if not cap.isOpened():
        print(f"Index {i}: [CLOSED]")
        continue
    ret, frame = cap.read()
    if ret:
        fname = out_dir / f"probe_index_{i}.jpg"
        cv2.imwrite(str(fname), frame)
        std = frame.std()
        print(f"Index {i}: [OPEN] - StdDev={std:.2f} - Saved to {fname}")
    else:
        print(f"Index {i}: [NO FRAME]")
    cap.release()
