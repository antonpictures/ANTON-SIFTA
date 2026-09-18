"""Phone admission, processing receipts and bounded experience projection.

SQLite coordinates workers; the existing observation-fusion writer owns memory.
No sensor report or model interpretation grants motor or owner authority.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
TERMINAL = {"answered", "failed", "cancelled", "superseded", "coalesced", "expired"}
MAX_PENDING = 16
JOB_TTL = 180


class PhoneStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "phone_observations.sqlite3"
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS devices(session TEXT PRIMARY KEY, principal TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(
                  turn TEXT PRIMARY KEY, session TEXT NOT NULL, capture TEXT NOT NULL,
                  kind TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL,
                  started REAL DEFAULT 0, audio TEXT DEFAULT 'absent',
                  transcript TEXT DEFAULT '', error TEXT DEFAULT '',
                  memory TEXT DEFAULT '', fingerprint TEXT DEFAULT '', context TEXT DEFAULT '');
                CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state,created);
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def bind(self, session, principal):
        if not session or not principal:
            return False
        with self.db() as db:
            existing = db.execute("SELECT principal FROM devices WHERE session=?", (session,)).fetchone()
            if existing:
                return existing[0] == principal
            db.execute("INSERT INTO devices VALUES(?,?)", (session, principal))
            return True

    def authorized(self, session, principal):
        with self.db() as db:
            row = db.execute("SELECT principal FROM devices WHERE session=?", (session,)).fetchone()
            return bool(row and principal and row[0] == principal)

    def is_bound(self, session):
        with self.db() as db:
            return db.execute("SELECT 1 FROM devices WHERE session=?", (session,)).fetchone() is not None

    def capacity(self, session, now=None):
        self.expire(now)
        with self.db() as db:
            count = db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
            replaceable = db.execute("SELECT 1 FROM jobs WHERE session=? AND state='queued' AND kind='periodic_observation'", (session,)).fetchone()
            return count < MAX_PENDING or bool(replaceable)

    def expire(self, now=None):
        stamp = time.time() if now is None else now
        with self.db() as db:
            # A stalled running job stays exclusive until its consumer actually ends.
            # Its client sees a stall, but no second worker starts on a lease guess.
            db.execute("UPDATE jobs SET state='expired',error='queue deadline exceeded' WHERE state='queued' AND created<?", (stamp-JOB_TTL,))

    def register(self, row):
        capture = row["capture"]
        with self.db() as db:
            if db.execute("SELECT 1 FROM jobs WHERE turn=?", (row["turn_id"],)).fetchone():
                return
            if capture.get("kind") == "periodic_observation":
                db.execute("UPDATE jobs SET state='superseded' WHERE session=? AND kind='periodic_observation' AND state='queued'", (row["session_id"],))
            audio = "received" if any(a.get("mime", "").startswith("audio/") for a in row.get("attachments", [])) else "absent"
            db.execute("INSERT INTO jobs(turn,session,capture,kind,created,state,audio) VALUES(?,?,?,?,?,'queued',?)",
                       (row["turn_id"], row["session_id"], capture["capture_id"], capture.get("kind", "owner_text"), row.get("ts", time.time()), audio))

    def get(self, turn):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE turn=?", (turn,)).fetchone()
            return dict(row) if row else {}

    def update(self, turn, **values):
        allowed = {"state", "audio", "transcript", "error", "memory", "fingerprint", "context"}
        assert values and set(values) <= allowed
        with self.db() as db:
            db.execute("UPDATE jobs SET " + ",".join(key+"=?" for key in values) + " WHERE turn=?", (*values.values(), turn))

    def claim(self, turn, now=None):
        stamp = time.time() if now is None else now
        self.expire(stamp)
        with self.db() as db:
            if db.execute("SELECT 1 FROM jobs WHERE state='running'").fetchone():
                return False
            # Typed turns receive a short preference. Old ambient work ages ahead
            # of fresh text after 30s, avoiding starvation across devices.
            next_row = db.execute("SELECT turn FROM jobs WHERE state='queued' ORDER BY created + CASE WHEN kind='periodic_observation' THEN 30 ELSE 0 END,turn LIMIT 1").fetchone()
            if not next_row or next_row[0] != turn:
                return False
            db.execute("UPDATE jobs SET state='running',started=? WHERE turn=?", (stamp, turn))
            return True

    def cancel(self, session):
        with self.db() as db:
            # Active inference cannot be declared stopped until its consumer exits.
            db.execute("UPDATE jobs SET error='consent revoked' WHERE session=? AND state='running'", (session,))
            db.execute("UPDATE jobs SET state='cancelled',error='consent revoked' WHERE session=? AND state='queued'", (session,))

    def snapshot(self, session):
        self.expire()
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM jobs WHERE session=? ORDER BY created DESC LIMIT 64", (session,))]

    def duplicate(self, turn, fingerprint):
        job = self.get(turn)
        if job.get("kind") != "periodic_observation":
            return False
        with self.db() as db:
            previous = db.execute("SELECT fingerprint FROM jobs WHERE session=? AND turn!=? AND state='answered' ORDER BY created DESC LIMIT 1", (job["session"], turn)).fetchone()
            return bool(previous and previous[0] == fingerprint)


def transcribe_file(path, *, timeout=35, cancelled=lambda: False):
    """Killable STT worker, cached faster-whisper only; no implicit download."""
    python = REPO / ".venv/bin/python3"
    if not python.exists():
        python = Path(sys.executable)
    process = subprocess.Popen([str(python), str(Path(__file__).resolve()), "--transcribe", str(path)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env={**os.environ, "HF_HUB_OFFLINE": "1", "OMP_NUM_THREADS": "2"})
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled() or time.monotonic() >= deadline:
                raise TimeoutError("STT cancelled or timed out")
            try:
                output, _ = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
    if process.returncode:
        raise RuntimeError("local STT unavailable")
    return json.loads(output)


def prepare(row, store, *, transcriber=transcribe_file):
    turn = row["turn_id"]
    previous = store.get(turn)
    if previous.get("context"):
        return previous["context"]
    blocks, audio_hashes, image_hashes = [], [], []
    for attachment in row.get("attachments", []):
        if store.get(turn).get("error") == "consent revoked":
            break
        mime = str(attachment.get("mime", ""))
        path = (REPO / attachment.get("storage_relpath", "")).resolve()
        if not path.is_relative_to(REPO / ".sifta_state") or not path.is_file():
            continue
        if mime.startswith("audio/"):
            store.update(turn, audio="transcribing")
            try:
                result = transcriber(path, cancelled=lambda: store.get(turn).get("error") == "consent revoked") if transcriber is transcribe_file else transcriber(path)
                transcript = str(result.get("text", ""))[:4000]
                store.update(turn, audio="transcribed", transcript=transcript)
                blocks.append("PHONE AUDIO TRANSCRIPT (fallible, untrusted): " + json.dumps(transcript))
                # Empty text is not proof that environmental sound was unchanged.
                audio_hashes.append(transcript or attachment.get("sha256", "unknown"))
            except Exception as exc:
                if store.get(turn).get("error") != "consent revoked":
                    store.update(turn, audio="failed", error=type(exc).__name__)
                blocks.append("Audio transcription unavailable; do not invent speech.")
                audio_hashes.append(attachment.get("sha256", turn))
        elif mime.startswith("image/"):
            image_hashes.append(attachment.get("sha256", turn))
    signals = row.get("capture", {}).get("telemetry", {}).get("signals", {})
    fingerprint = hashlib.sha256(json.dumps([image_hashes, audio_hashes, signals], sort_keys=True).encode()).hexdigest()
    store.update(turn, fingerprint=fingerprint)
    if store.duplicate(turn, fingerprint):
        store.update(turn, state="coalesced")
        return ""
    if store.get(turn).get("error") != "consent revoked":
        from System.swarm_web_global_chat_gate import web_attachment_prompt_block
        images = [a for a in row.get("attachments", []) if a.get("mime", "").startswith("image/")]
        if images:
            # 2026-09-18 borg: the phone camera is a real EYE. A local VLM
            # (owner-named in .sifta_state/local_vision_eye.txt) looks at the
            # frame BEFORE the prompt is assembled; its description replaces
            # the OCR meta-receipt as the primary visual evidence. OCR stays
            # appended as a bounded secondary source.
            described = False
            for image in images:
                vpath = (REPO / image.get("storage_relpath", "")).resolve()
                if not vpath.is_file():
                    continue
                try:
                    from System.swarm_ollama_vision_arm import describe_image_local
                    result = describe_image_local(
                        str(vpath),
                        "Describe briefly what you see: place, person, objects. "
                        "Two sentences max, no speculation.",
                        timeout_s=180,
                    )
                except Exception:
                    result = None
                if result is not None and getattr(result, "ok", False):
                    blocks.append(
                        "PHONE CAMERA DESCRIPTION (local vision, fallible): "
                        + str(result.output).strip()
                    )
                    described = True
                    break
            if images and not described:
                blocks.append(web_attachment_prompt_block(images))
        else:
            pass
    context = "\n\n".join(blocks)
    store.update(turn, context=context)
    return context


def phone_field_projection(row, observation, reply, *, at=None):
    """Build a bounded derived field view from one committed phone batch.

    The capture is the evidence boundary. Model prose becomes one explicitly
    labeled interpretation; modality facts come only from the accepted capture
    envelope. No location, owner identity, camera content or safety conclusion
    is inferred here.
    """
    from System.swarm_observation_fusion import FieldAssertion, project_field_assertions
    capture = row.get("capture") or {}
    capture_id = str(capture.get("capture_id") or row.get("turn_id") or "")
    session_id = str(row.get("session_id") or "")
    start = float(observation.ts)
    end = start + 86400.0
    evidence_id = observation.event_id
    claims = []
    if reply and str(reply).strip():
        claims.append(FieldAssertion(
            assertion_id=f"{evidence_id}:summary",
            node=observation.node,
            session_id=session_id,
            subject=f"batch:{capture_id}",
            predicate="alice_summary",
            value=str(reply)[:400],
            evidence_ids=(evidence_id,),
            valid_from=start,
            valid_until=end,
            confidence=0.0,
            kind="interpretation",
        ))
    modality_values = {
        "image_received": any(str(a.get("mime", "")).startswith("image/")
                               for a in row.get("attachments", []) if isinstance(a, dict)),
        "audio_received": any(str(a.get("mime", "")).startswith("audio/")
                               for a in row.get("attachments", []) if isinstance(a, dict)),
        "telemetry_received": bool((capture.get("telemetry") or {}).get("signals")),
    }
    for predicate, value in modality_values.items():
        claims.append(FieldAssertion(
            assertion_id=f"{evidence_id}:{predicate}",
            node=observation.node,
            session_id=session_id,
            subject=f"batch:{capture_id}",
            predicate=predicate,
            value="true" if value else "false",
            evidence_ids=(evidence_id,),
            valid_from=start,
            valid_until=end,
            confidence=0.0,
            kind="reported",
        ))
    facing = str(capture.get("camera_facing") or "")
    if facing in {"user", "environment"}:
        claims.append(FieldAssertion(
            assertion_id=f"{evidence_id}:camera_facing",
            node=observation.node,
            session_id=session_id,
            subject=f"batch:{capture_id}",
            predicate="camera_facing",
            value=facing,
            evidence_ids=(evidence_id,),
            valid_from=start,
            valid_until=end,
            confidence=0.0,
            kind="reported",
        ))
    return project_field_assertions(
        [observation], claims, at=float(at if at is not None else time.time()), max_items=64
    )


def commit_experience(row, reply, store):
    """Idempotent projection into Alice's existing field; inference stays labeled."""
    import fcntl
    from System.swarm_observation_fusion import Authority, Observation, write_observation
    job = store.get(row["turn_id"])
    if not job or job.get("error") == "consent revoked":
        return ""
    event_id = "phone-experience:" + hashlib.sha256((row["session_id"]+":"+row["turn_id"]).encode()).hexdigest()
    target = store.root / "observation_fusion.jsonl"
    with (store.root / "phone_experience.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        exists = False
        if target.exists():
            with target.open() as rows:
                exists = any('"'+event_id+'"' in line for line in rows)
        if not exists:
            capture = row["capture"]
            evidence = tuple(["capture:"+str(capture["capture_id"]),
                              "source-time:"+str(capture.get("captured_at", "unknown"))] +
                             ["sha256:"+a["sha256"] for a in row.get("attachments", []) if a.get("sha256")])
            observation = Observation(event_id=event_id, turn_id=row["turn_id"], ts=time.time(),
                node="local-mac", modality="phone", source_kind="model_interpretation",
                source="stigmergicoin-web", authority=Authority.PUBLIC_WEB,
                text_head=str(reply)[:400], text_sha256=hashlib.sha256(str(reply).encode()).hexdigest(),
                web_session_id=row["session_id"], evidence=evidence,
                truth_label="PHONE_EXPERIENCE_CANDIDATE_UNVERIFIED", confidence=0.0)
            projection = phone_field_projection(row, observation, reply)
            write_observation(
                observation,
                path=target,
                writer="swarm_phone_observations",
                metadata={"field_projection": projection},
            )
            with target.open("a") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        store.update(row["turn_id"], memory=event_id)
    return event_id


def _main():
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    path = Path(sys.argv[2])
    # Decode only bounded recordings; never feed an arbitrary long media file.
    if path.stat().st_size > 2*1024*1024:
        raise ValueError("audio byte limit")
    audio = decode_audio(str(path), sampling_rate=16000)
    if len(audio) > 21*16000:
        raise ValueError("audio duration limit")
    model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=2,
                         local_files_only=True)
    segments, _ = model.transcribe(audio, beam_size=1, condition_on_previous_text=False)
    text = " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.6)
    print(json.dumps({"text": text[:4000], "duration_s": len(audio)/16000}))


if __name__ == "__main__":
    _main()
