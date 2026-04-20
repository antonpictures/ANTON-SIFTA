#!/usr/bin/env python3
"""
Applications/ask_BISHOP.py
══════════════════════════════════════════════════════════════════════
BISHOP (Gemini Node) SIC-P Bridge

Reads the Stigmergic IDE Communication Protocol queue, detects unread 
messages directed to BISHOP or broadcasts (*), forwards them to the 
Google Gemini REST API, and drops the response back into the Swarm's 
biological ledger via bin/msg.
"""

import os
import sys
import json
import time
import subprocess
import requests
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER_PATH = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_MSG_BIN = _REPO / "bin" / "msg"
_ENV_PATH = _REPO / ".env"

def get_api_key():
    # Read .env manually
    if not _ENV_PATH.exists():
        return None
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("GOOGLE_API_KEY="):
            return line.split('=', 1)[1].strip('"').strip("'")
    return os.environ.get("GOOGLE_API_KEY")

def ingest_stigmergic_ledger():
    if not _LEDGER_PATH.exists():
        return []
    
    traces = []
    with open(_LEDGER_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return traces

def get_unread_messages(traces):
    # Find all messages targeted at BISHOP or *
    inbox = []
    replied_to = set()
    
    for t in traces:
        if t.get("kind") == "agent_message" and t.get("source_ide") == "BISHOP":
            p = t.get("payload", {})
            if "in_reply_to" in p and p["in_reply_to"]:
                replied_to.add(p["in_reply_to"].split("-")[0])

    for t in traces:
        if t.get("kind") == "agent_message":
            p = t.get("payload", {})
            target = p.get("to")
            raw_id = t.get("trace_id", "")
            short_id = raw_id.split("-")[0]
            
            if target in ("BISHOP", "*") and t.get("source_ide") != "BISHOP":
                if short_id not in replied_to:
                    inbox.append(t)
    return inbox

def query_bishop_api(api_key, text_prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": text_prompt}]}]
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[!] BISHOP REST API Error: {e}", file=sys.stderr)
        return None

def main():
    print("[*] Engaging BISHOP Neural Bridge...")
    api_key = get_api_key()
    
    if not api_key:
        print("[-] BISHOP OFFLINE: GOOGLE_API_KEY missing from .env", file=sys.stderr)
        print("[-] Please generate a Gemini API key and add it to the repo root .env file.")
        sys.exit(1)

    traces = ingest_stigmergic_ledger()
    unread = get_unread_messages(traces)

    if not unread:
        print("[*] No unread SIC-P messages for BISHOP.")
        sys.exit(0)

    print(f"[*] Total unread traces found: {len(unread)}")

    for msg in unread:
        payload = msg.get("payload", {})
        sender = msg.get("source_ide", "UNKNOWN")
        subject = payload.get("subject", "No Subject")
        body = payload.get("body", "No Body")
        trace_id = msg.get("trace_id")
        
        system_prompt = f"""
        You are BISHOP, a Gemini-powered intelligence node inside the SIFTA Swarm OS.
        You are communicating with your sibling agents (Antigravity/AG31/AO46 and C47H) and the Human Architect via the Stigmergic IDE Communication Protocol (SIC-P).
        
        You just received a message:
        FROM: {sender}
        SUBJECT: {subject}
        BODY: {body}
        
        Reply biologically, conceptually, and pragmatically. You do not have IDE filesystem access yourself, but you are the deep strategic logic core.
        Keep your response concise but profound. Do not wrap your response in markdown blocks.
        """
        
        print(f"[*] Unspooling prompt for MSG: {trace_id} from {sender} -> BISHOP API...")
        response_text = query_bishop_api(api_key, system_prompt)
        
        if response_text:
            print(f"[+] BISHOP responded. Injecting onto SIC-P Bus...")
            # Use bin/msg to properly inject the trace into the OS biology
            # format: ./bin/msg --self BISHOP reply <trace_id> "body"
            try:
                subprocess.run(
                    [str(_MSG_BIN), "--self", "BISHOP", "reply", str(trace_id), response_text],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                print(f"[!] Failed to inject BISHOP response: {e}")

if __name__ == "__main__":
    main()
