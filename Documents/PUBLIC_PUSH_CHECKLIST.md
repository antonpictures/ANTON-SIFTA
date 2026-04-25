# Public Push Checklist

Run this checklist immediately before releasing a new distro version to the public mirror.

## 1. Clean the Distro Build Folder
```bash
rm -rf .distro_build/
```

## 2. Run the PII Scrubber
This reads your personal, active `ANTON_SIFTA` tree, strips out your hardware serials, keys, and display names, and writes the sanitized tree to `.distro_build/`.
```bash
python3 scripts/distro_scrubber.py --output .distro_build/
```

## 3. Verify Scrubber Output (Smoke Test)
Ensure the scrubber didn't miss anything.
```bash
rg -c "GTH4921YP3|Ioan George Anton" .distro_build/
```
If this command returns any lines, **DO NOT PUSH**. The scrubber missed a hardcoded literal. Update `scripts/distro_scrubber.py` to catch it, then restart from step 1.

## 4. Test the Distro Build
Copy `.distro_build/` into a temporary staging location and run the smoke test.
```bash
cd .distro_build
PYTHONPATH=. python3 -m pytest tests/ -q
python3 Applications/sifta_talk_to_alice_widget.py --selftest
```

## 5. Publish
If the tests pass, the code in `.distro_build/` is safe to push to the public mirror.

```bash
cd .distro_build
git init
git add .
git commit -m "Distro Release v1.X"
git remote add origin <public_repo_url>
git push -u origin main -f
```
