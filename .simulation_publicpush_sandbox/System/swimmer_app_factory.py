#!/usr/bin/env python3
"""
System/swimmer_app_factory.py — Swimmer App Factory
════════════════════════════════════════════════════════
The missing loop: Chat → Code → Validate → Register → Mint → Notify.

When the Architect types "build: a soccer game" in Swarm Chat,
this engine dispatches local Ollama to generate a complete PyQt6 widget,
validates it surgically, writes it to Applications/swimmer_built/,
registers it in the manifest, mints STGM, and signals back "it's ready."
"""

import ast
import json
import os
import re
import subprocess
import sys
import time
import hashlib
import urllib.request
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

_REPO = Path(__file__).resolve().parent.parent
_SYSTEM = _REPO / "System"
if str(_SYSTEM) not in sys.path:
    sys.path.insert(0, str(_SYSTEM))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

APPS_DIR = _REPO / "Applications" / "swimmer_built"
CRUCIBLE_DIR = _REPO / "System" / "Crucible"
MANIFEST_PATH = _REPO / "Applications" / "apps_manifest.json"

# ── Security Blocklist ─────────────────────────────────────────────────────
# Generated apps must NEVER touch these patterns.
BANNED_PATTERNS = [
    r'\bos\.system\b',
    r'\bsubprocess\.',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'\b__import__\s*\(',
    r'repair_log\.jsonl',
    r'crypto_keychain',
    r'\.sifta_state',
    r'ed25519',
    r'sign_block',
    r'shutil\.rmtree',
]

# ── Prompt Template ────────────────────────────────────────────────────────
APP_FACTORY_PROMPT = """\
You are a PyQt6 application developer for the SIFTA Swarm OS.
Generate a COMPLETE, SELF-CONTAINED Python file that implements the user's request as a PyQt6 desktop widget.

RULES — follow these EXACTLY or the build will be rejected:

1. The file MUST start with these exact imports:
   ```python
   import sys
   from pathlib import Path
   _REPO = Path(__file__).resolve().parent.parent.parent
   if str(_REPO) not in sys.path:
       sys.path.insert(0, str(_REPO))
   from System.sifta_base_widget import SiftaBaseWidget
   from PyQt6.QtWidgets import *
   from PyQt6.QtCore import *
   from PyQt6.QtGui import *
   ```

2. You MUST define exactly ONE class that inherits SiftaBaseWidget.
3. The class MUST have `APP_NAME = "Your App Title"` as a class attribute.
4. The class MUST implement `def build_ui(self, layout: QVBoxLayout) -> None:`.
5. ALL your UI code goes inside build_ui(). Do NOT override __init__.
6. Use QTimer for animations and game loops (self.make_timer(ms, callback)).
7. Use QPainter for custom graphics inside a QWidget's paintEvent.
8. DO NOT use subprocess, os.system, eval, exec, or __import__.
9. DO NOT import anything outside PyQt6 and standard library (math, random, time, etc).
10. The file MUST end with a standalone runner block:
    ```python
    if __name__ == "__main__":
        from PyQt6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        w = YourClassName()
        w.resize(900, 700)
        w.show()
        sys.exit(app.exec())
    ```

11. Respond with ONLY the Python code inside a ```python ... ``` block. No explanation.
12. Make the app visually rich: use colors, animations, and interactivity. NOT a boring placeholder.

USER REQUEST:
{user_request}
"""


def _slugify(name: str) -> str:
    """Convert 'My Cool App' to 'my_cool_app'."""
    s = re.sub(r'[^a-zA-Z0-9\s]', '', name).strip().lower()
    return re.sub(r'\s+', '_', s)


def _extract_python_code(raw: str) -> Optional[str]:
    """Pull the largest ```python...``` block from LLM output."""
    blocks = re.findall(r'```(?:python)?\n?(.*?)```', raw, re.DOTALL | re.IGNORECASE)
    if blocks:
        return max(blocks, key=len).strip()
    # Maybe the model returned raw code with no fences
    if 'class ' in raw and 'SiftaBaseWidget' in raw:
        return raw.strip()
    return None


def _security_scan(code: str) -> Optional[str]:
    """Returns error string if code contains banned patterns, else None."""
    for pattern in BANNED_PATTERNS:
        match = re.search(pattern, code)
        if match:
            return f"Security violation: banned pattern '{match.group()}' detected"
    return None


def _ast_validate(code: str) -> Optional[str]:
    """Returns error string if code has syntax errors, else None."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"Syntax error: {e}"


def _extract_class_info(code: str) -> Optional[dict]:
    """Parse the AST to find the SiftaBaseWidget subclass and its APP_NAME."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if it inherits from SiftaBaseWidget
            for base in node.bases:
                base_name = ""
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name == "SiftaBaseWidget":
                    # Find APP_NAME
                    app_name = node.name  # fallback to class name
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == "APP_NAME":
                                    if isinstance(item.value, ast.Constant):
                                        app_name = item.value.value
                    return {
                        "class_name": node.name,
                        "app_name": app_name,
                    }
    return None


def _import_test(filepath: Path) -> Optional[str]:
    """Try importing the file as a module. Returns error or None."""
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, '{filepath.parent}'); "
             f"sys.path.insert(0, '{_REPO}'); "
             f"import {filepath.stem}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            # Ignore missing third-party deps that aren't local
            if "ModuleNotFoundError" in stderr:
                mod_match = re.search(r"No module named '([^']+)'", stderr)
                if mod_match:
                    missing = mod_match.group(1).split(".")[0]
                    # If it's a PyQt6 display issue (no display), that's OK
                    if "display" in stderr.lower() or "xcb" in stderr.lower():
                        return None
                    return f"Import failed — missing module: {missing}"
            return f"Import failed: {stderr[-300:]}"
        return None
    except subprocess.TimeoutExpired:
        return "Import test timed out (possible infinite loop)"
    except Exception as e:
        return f"Import test error: {e}"


def _register_manifest(app_name: str, class_name: str, filename: str) -> None:
    """Append the new app to apps_manifest.json."""
    manifest = {}
    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text())
        except Exception:
            pass

    manifest[app_name] = {
        "category": "Swimmer Built",
        "entry_point": f"Applications/swimmer_built/{filename}",
        "widget_class": class_name,
        "window_width": 900,
        "window_height": 700,
        "signature": "SWIMMER_FACTORY",
    }

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def _mint_stgm(app_name: str, model: str) -> None:
    """Mint STGM reward for building a working app."""
    try:
        from inference_economy import mint_reward
        mint_reward(
            agent_id="M5SIFTA_BODY",
            action=f"APP_FACTORY::{app_name}",
            file_repaired=f"Applications/swimmer_built/{_slugify(app_name)}.py",
            model=model,
        )
    except Exception as e:
        print(f"[APP_FACTORY] Mint failed (non-fatal): {e}")


class AppFactoryWorker(QThread):
    """
    QThread that generates, validates, and registers a swimmer-built app.
    Emits progress updates and final result back to the chat UI.
    """
    progress = pyqtSignal(str)       # status updates for chat bubbles
    build_complete = pyqtSignal(str)  # success message
    build_failed = pyqtSignal(str)   # failure message

    def __init__(self, user_request: str, model: str = "gemma4:latest"):
        super().__init__()
        self.user_request = user_request
        self.model = model
        self.max_retries = 3

    def run(self):
        self.progress.emit("🏗️ Swimmers dispatched. Building your app...")

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            self.progress.emit(f"⚙️ Attempt {attempt}/{self.max_retries}...")

            # ── 1. Call Ollama ──────────────────────────────────────
            prompt = APP_FACTORY_PROMPT.format(user_request=self.user_request)
            if attempt > 1 and last_error:
                prompt += (
                    f"\n\nIMPORTANT: Your previous attempt failed validation:\n"
                    f"  ERROR: {last_error}\n"
                    f"Fix the issue and regenerate the COMPLETE file."
                )

            raw_response = self._call_ollama(prompt)
            if not raw_response:
                last_error = "Ollama returned empty response"
                continue

            # ── 2. Extract code ─────────────────────────────────────
            code = _extract_python_code(raw_response)
            if not code:
                last_error = "Could not extract Python code from LLM response"
                continue

            # ── 3. Size guard ───────────────────────────────────────
            line_count = len(code.splitlines())
            if line_count > 500:
                last_error = f"Hallucination guard: {line_count} lines (max 500)"
                continue

            # ── 4. Security scan ────────────────────────────────────
            sec_err = _security_scan(code)
            if sec_err:
                last_error = sec_err
                continue

            # ── 5. AST validation ───────────────────────────────────
            ast_err = _ast_validate(code)
            if ast_err:
                last_error = ast_err
                continue

            # ── 6. Extract class info ───────────────────────────────
            info = _extract_class_info(code)
            if not info:
                last_error = "No SiftaBaseWidget subclass found in generated code"
                continue

            app_name = info["app_name"]
            class_name = info["class_name"]
            slug = _slugify(app_name)
            filename = f"{slug}.py"
            filepath = APPS_DIR / filename

            # ── 7. Write to Crucible Sandbox ─────────────────────────
            CRUCIBLE_DIR.mkdir(parents=True, exist_ok=True)
            filepath = CRUCIBLE_DIR / filename
            filepath.write_text(code + "\n", encoding="utf-8")

            # ── 8. Import test ──────────────────────────────────────
            import_err = _import_test(filepath)
            if import_err:
                last_error = import_err
                filepath.unlink(missing_ok=True)  # Clean up broken file
                continue

            # ── 9. Skip Manifest (Wait for Approval) ────────────────
            # We do NOT call _register_manifest here. The app stays in
            # the Crucible until the Architect explicitly approves it.

            # ── 10. Mint STGM ───────────────────────────────────────
            _mint_stgm(app_name, self.model)

            self.build_complete.emit(
                f"✅ App '{app_name}' built and placed in the Crucible Sandbox.\n"
                f"🧪 Type `sandbox {slug}` to test it.\n"
                f"✅ Type `approve {slug}` to add it to your Programs menu.\n"
                f"❌ Type `reject {slug} <reason>` to delete and rebuild."
            )
            return

        # All retries exhausted
        self.build_failed.emit(
            f"❌ Build failed after {self.max_retries} attempts.\n"
            f"Last error: {last_error}"
        )

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Streaming Ollama call — collects full response."""
        url = "http://127.0.0.1:11434/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.3,
            "keep_alive": "2m",
            "num_predict": 4096,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        full_response = []
        in_think = False
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("response", "")

                    if "<think>" in token:
                        in_think = True
                    if "</think>" in token:
                        in_think = False
                        continue
                    if in_think:
                        continue  # Skip reasoning tokens

                    full_response.append(token)

                    if chunk.get("done"):
                        break

            return "".join(full_response).strip() or None

        except Exception as e:
            self.progress.emit(f"⚠️ Ollama error: {e}")
            return None
