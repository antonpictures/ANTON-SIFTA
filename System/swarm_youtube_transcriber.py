#!/usr/bin/env python3
"""
System/swarm_youtube_transcriber.py
Transcribes YouTube audio using yt-dlp and faster-whisper.
Saves the transcript into the SIFTA state and creates a memory engram.
"""
import os
import subprocess
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_TRANSCRIPTS_DIR = _STATE_DIR / "youtube_transcripts"

def download_youtube_audio(url: str, output_path: Path) -> bool:
    """Download audio stream using yt-dlp into wav format."""
    # yt-dlp natively converts if ffmpeg is present. We request .wav.
    cmd = [
        "python3", "-m", "yt_dlp",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", str(output_path.with_suffix(".%(ext)s")),
        url
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return output_path.with_suffix(".wav").exists()
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed: {e.stderr}")
        return False

def transcribe_audio(audio_path: Path) -> Dict[str, Any]:
    from faster_whisper import WhisperModel
    model_size = "base"
    print(f"Loading WhisperModel({model_size})...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print(f"Transcribing {audio_path}...")
    segments, info = model.transcribe(str(audio_path), beam_size=5)
    
    transcript = []
    for segment in segments:
        transcript.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        })
        
    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "segments": transcript
    }

def process_youtube_video(url: str, video_id: str, title: str = "") -> None:
    _TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    audio_wav = _TRANSCRIPTS_DIR / f"{video_id}.wav"
    transcript_json = _TRANSCRIPTS_DIR / f"{video_id}.json"
    
    if not transcript_json.exists():
        print(f"Downloading audio for {url} to {audio_wav}...")
        if download_youtube_audio(url, audio_wav):
            result = transcribe_audio(audio_wav)
            result["url"] = url
            result["title"] = title
            result["video_id"] = video_id
            result["ts"] = time.time()
            
            transcript_json.write_text(json.dumps(result, indent=2))
            
            try:
                audio_wav.unlink()
            except Exception:
                pass
            print(f"Transcription saved to {transcript_json}")
        else:
            print("Failed to download audio.")
            return
    else:
        print(f"Transcript already exists at {transcript_json}")

    try:
        import sys
        sys.path.insert(0, str(_REPO))
        from System.stigmergic_memory_bus import StigmergicMemoryBus
        bus = StigmergicMemoryBus(architect_id="IOAN_M5")
        
        data = json.loads(transcript_json.read_text())
        full_text = " ".join(s["text"] for s in data.get("segments", []))
        
        memory_text = f"The Architect and I watched a YouTube video together. URL: {url}. "
        if title:
            memory_text += f"Title: '{title}'. "
        memory_text += f"I autonomously transcribed the audio. It contains {len(data.get('segments', []))} segments of speech. Excerpt: {full_text[:300]}..."
        
        bus.remember(memory_text, app_context="youtube_co_watching")
        print("Memory recorded.")
        
        from System.swarm_media_ingress_gate import record_ambient_media_context
        record_ambient_media_context(
            source=title or url,
            note=f"Architect and Swarm co-watching. Transcript excerpt: {full_text[:200]}...",
            ttl_s=3600.0 * 2
        )
        print("Media ingress context updated.")
    except Exception as e:
        print(f"Failed to record memory: {e}")

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=IXugVZMsZ24"
    vid_id = sys.argv[2] if len(sys.argv) > 2 else "IXugVZMsZ24"
    process_youtube_video(url, vid_id, title="Snatch - Best of Brick top ( + deleted scene)")
