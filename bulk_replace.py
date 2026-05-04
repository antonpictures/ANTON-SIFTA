import os

REPLACEMENTS = {
    '"sifta-gemma4-alice:latest"': '"sifta-gemma4-alice:latest"',
    "'sifta-gemma4-alice:latest'": "'sifta-gemma4-alice:latest'",
    '"qwen3.5:2b"': '"qwen3.5:2b"',
    "'qwen3.5:2b'": "'qwen3.5:2b'",
    '"qwen3.5:2b"': '"qwen3.5:2b"',
    "'qwen3.5:2b'": "'qwen3.5:2b'",
}

def process_file(path):
    if os.path.islink(path): return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return
        
    orig = content
    for old, new in REPLACEMENTS.items():
        content = content.replace(old, new)
        
    if orig != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {path}")

for root, dirs, files in os.walk('.'):
    # skip hidden and Archive
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'Archive']
    for file in files:
        if file.endswith('.py') or file.endswith('.md') or file.endswith('.sh') or file.endswith('.yaml') or file.endswith('.txt'):
            process_file(os.path.join(root, file))

print("Done.")
