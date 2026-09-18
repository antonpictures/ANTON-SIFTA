"""Exercise the actual script entrypoint without loading a speech model."""
import os
from pathlib import Path
import subprocess
import sys


def test_standalone_stt_worker_has_no_repository_import_dependency(tmp_path):
    script = Path(__file__).resolve().parents[1] / "System/swarm_phone_observations.py"
    audio = tmp_path / "stub.mp4"
    audio.write_bytes(b"synthetic")
    code = '''
import runpy, sys, types
m = types.ModuleType("faster_whisper")
m.WhisperModel = lambda *a, **k: types.SimpleNamespace(transcribe=lambda *a, **k: ([], {}))
a = types.ModuleType("faster_whisper.audio")
a.decode_audio = lambda *a, **k: []
sys.modules["faster_whisper"] = m
sys.modules["faster_whisper.audio"] = a
script, audio = sys.argv[1:]
sys.argv = [script, "--transcribe", audio]
runpy.run_path(script, run_name="__main__")
'''
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out = subprocess.run([sys.executable, "-I", "-c", code, str(script), str(audio)],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert out.returncode == 0, out.stderr
    assert '"text": ""' in out.stdout
