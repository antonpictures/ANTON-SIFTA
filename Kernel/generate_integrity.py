import json
import hashlib
import os

manifest = {"_comment": "Non-Proliferation SIFTA Integrity Manifest (Auto-Generated)"}
kernel_dir = "Kernel"

for f in os.listdir(kernel_dir):
    if f.endswith(".py"):
        filepath = os.path.join(kernel_dir, f)
        with open(filepath, "rb") as file_bytes:
            sha256_hash = hashlib.sha256(file_bytes.read()).hexdigest()
            manifest[f] = sha256_hash

manifest_path = os.path.join(kernel_dir, "integrity_manifest.json")
with open(manifest_path, "w") as out:
    json.dump(manifest, out, indent=2)

print("Integrity Manifest Generated successfully.")
