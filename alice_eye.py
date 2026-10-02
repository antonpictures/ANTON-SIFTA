#!/usr/bin/env python3
"""alice_eye.py - a text-only mind looking through a local vision model.

The reasoning model behind this harness is text-only: the image reaches it and is
dropped. A vision-language model running locally is not text-only. This script is
the nerve between them: it hands the pixels to a local VLM and returns words.

    python3 alice_eye.py <image-path-or-sha> ["question"]
    cat shot.jpg | python3 alice_eye.py - "what is on screen?"

Nothing leaves the machine: this talks to the local ollama daemon only.
Answers a question; with no question it describes what is present.
"""
import argparse
import base64
import glob
import json
import os
import sys
import urllib.error
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
# strongest installed vision model first, small fast one as fallback
DEFAULT_MODEL = "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M"
FALLBACK_MODEL = "hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0"
STORE = os.path.join(os.environ.get("DSH_HOME", os.path.expanduser("~/.dsh")),
                     "attachments", "v1", "objects")
EXOTIC_SPACE = {0x202F: " ", 0x00A0: " ", 0x2007: " ", 0x2009: " ", 0x3000: " "}


def normalise(s):
    return s.translate(EXOTIC_SPACE)


def resolve(arg):
    """Accept a path (U+202F-tolerant), a sha256 prefix, or '-' for stdin."""
    for cand in (arg, normalise(arg)):
        if os.path.isfile(cand):
            return cand
    if os.sep in normalise(arg):
        hits = glob.glob(normalise(arg))
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise SystemExit("ambiguous path %r matches:\n  %s"
                             % (arg, "\n  ".join(sorted(hits))))

    prefix = normalise(arg).lower()
    for tag in ("sha256:", "attach_sha256:", "blob:", "objects/"):
        if tag in prefix:
            prefix = prefix.split(tag, 1)[1]
    prefix = prefix.strip()
    if all(c in "0123456789abcdef" for c in prefix) and len(prefix) >= 2:
        for d in sorted(os.listdir(STORE)):
            full = os.path.join(STORE, d)
            if not os.path.isdir(full):
                continue
            for name in sorted(os.listdir(full)):
                if name.startswith(prefix):
                    return os.path.join(full, name)
    raise SystemExit("no such image: %r" % arg)


def installed_vision_models():
    with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as r:
        tags = json.load(r)
    return [m["name"] for m in tags.get("models", [])]


def ask(model, image_b64, prompt, timeout):
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode()
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r).get("response", "").strip()


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("image")
    ap.add_argument("question", nargs="?", default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("-h", "--help", action="help")
    a = ap.parse_args()

    if a.image == "-":
        raw = sys.stdin.buffer.read()
        if not raw:
            raise SystemExit("stdin was empty")
        label = "<stdin>"
    else:
        path = resolve(a.image)
        raw = open(path, "rb").read()
        label = path

    question = a.question or (
        "Describe this image precisely and concretely: what is it, what is "
        "happening, and what text is visible? Be specific and literal.")
    b64 = base64.b64encode(raw).decode()

    try:
        models = installed_vision_models()
    except urllib.error.URLError as e:
        raise SystemExit("ollama daemon unreachable at %s (%s)\n"
                         "  start it with: ollama serve" % (OLLAMA, e))

    tried = []
    for model in (a.model, FALLBACK_MODEL):
        if model in tried:
            continue
        tried.append(model)
        if model not in models:
            print("[skip] %s is not installed" % model, file=sys.stderr)
            continue
        try:
            answer = ask(model, b64, question, a.timeout)
        except Exception as e:  # model-specific failure: try the next one
            print("[fail] %s: %s" % (model, e), file=sys.stderr)
            continue
        if answer:
            print("image   %s" % label)
            print("bytes   %d" % len(raw))
            print("eye     %s" % model)
            print("asked   %s" % question)
            print("-" * 60)
            print(answer)
            return
        print("[empty] %s returned nothing" % model, file=sys.stderr)

    raise SystemExit("no local vision model produced an answer; tried: %s"
                     % ", ".join(tried))


if __name__ == "__main__":
    main()
